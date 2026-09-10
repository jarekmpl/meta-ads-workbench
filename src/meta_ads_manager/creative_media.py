"""Cache owned creative media locally; never forward Graph credentials to a CDN."""

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from meta_ads_manager.creative_review import CreativeAPI, Evidence
from meta_ads_manager.errors import AppError
from meta_ads_manager.meta_connection import load_credentials, save_private
from meta_ads_manager.meta_provider import validate_scope
from meta_ads_manager.report_layout import materials_directory


class StopRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_media_url(url):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    domains = ("fbcdn.net", "fbsbx.com", "cdninstagram.com")
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or parsed.port not in (None, 443)
            or not any(host == d or host.endswith("." + d) for d in domains)
            or "access_token" in parse_qs(parsed.query)):
        raise AppError("MEDIA_URL", "Adres materiału nie jest dozwolonym adresem CDN Meta.", 5)


def download(url, directory, max_bytes=150_000_000):
    opener = build_opener(StopRedirect())
    for _ in range(6):
        check_media_url(url)
        try:
            with opener.open(Request(url, method="GET"), timeout=60) as response:
                mime = response.headers.get_content_type()
                extensions = {"image/jpeg": ".jpg", "image/png": ".png",
                              "image/webp": ".webp", "video/mp4": ".mp4"}
                if mime not in extensions:
                    raise AppError("MEDIA_TYPE", "Nieobsługiwany typ materiału.", 5)
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise AppError("MEDIA_SIZE", "Materiał przekracza limit rozmiaru.", 5)
                digest = hashlib.sha256(body).hexdigest()
                path = directory / (digest + extensions[mime])
                if not path.exists():
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, "wb") as handle:
                        handle.write(body)
                return {"file": path.name, "sha256": digest, "bytes": len(body), "mime": mime}
        except HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308) and exc.headers.get("Location"):
                url = urljoin(url, exc.headers["Location"])
                continue
            raise AppError("MEDIA_HTTP", "Nie udało się odczytać materiału CDN.", 5) from None
        except (URLError, OSError, TimeoutError):
            raise AppError("MEDIA_NETWORK", "Nie udało się pobrać materiału CDN.", 5) from None
    raise AppError("MEDIA_REDIRECT", "Przekroczono limit przekierowań CDN.", 5)


def walk(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


def existing_post(evidence, api, creative):
    """The post ID must come from an already account-validated creative."""
    post_id = creative.get("effective_object_story_id")
    if not post_id:
        return None
    api.allow(post_id)
    post = evidence.fetch(f"post-{post_id}", api, post_id, {
        "fields": "id,message,full_picture,attachments{media,subattachments,title,type}",
    }, many=False, optional=True)
    if post and post.get("id") != post_id:
        raise AppError("SCOPE_MISMATCH", "Zwrócono inny post.", 3)
    return post


def prepare_frames(media_dir, asset):
    """Evidence frames only: not a claim of reviewing motion or listening to audio."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        return {"status": "dependency_missing"}
    file = media_dir / asset["file"]
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(file)],
        capture_output=True, timeout=30, check=False,
    )
    if probe.returncode:
        return {"status": "probe_failed"}
    data = json.loads(probe.stdout)
    duration = float(data["format"]["duration"])
    timestamps = sorted({round(x, 2) for x in (0, 1, 2, 3, duration / 4,
                                              duration / 2, duration * .75, duration - .2)
                         if 0 <= x < duration})
    frames = []
    for i, moment in enumerate(timestamps):
        out = media_dir / f'{asset["sha256"]}-frame-{i:02d}.jpg'
        if not out.exists():
            result = subprocess.run(
                ["ffmpeg", "-v", "error", "-ss", str(moment), "-i", str(file), "-frames:v", "1",
                 "-vf", "scale=960:-2", "-y", str(out)],
                capture_output=True, timeout=60, check=False,
            )
            if result.returncode or not out.exists():
                continue
            out.chmod(0o600)
        frames.append({"time_seconds": moment, "file": out.name})
    return {"status": "frames_prepared", "duration_seconds": duration, "frames": frames,
            "audio_present": any(s["codec_type"] == "audio" for s in data["streams"]),
            "audio_review": "not_reviewed", "transcript": None}


def collect_media(args):
    p = materials_directory(args.directory)
    collection = json.loads((p / "collection.json").read_text())
    if (collection["client_id"], collection["account_id"]) != (args.client, args.account):
        raise AppError("SCOPE_MISMATCH", "Inne konto w kolekcji kreacji.", 3)
    connection = validate_scope(Path.cwd(), args.client, args.account)
    api = CreativeAPI(connection, load_credentials(Path.cwd(), connection))
    evidence = Evidence(p, json.loads((p / "scope.json").read_text()))
    media_dir = p / "media"
    media_dir.mkdir(exist_ok=True, mode=0o700)
    cache_file = p / "media-downloads.json"
    cached = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    cards = []
    for ad_id in collection["selected_ad_ids"]:
        source = p / f"ad-{ad_id}.json"
        if not source.exists():
            cards.append({"ad_id": ad_id, "status": "settings_unavailable", "assets": []})
            continue
        ad = json.loads(source.read_text())["data"]
        if ad["account_id"] != args.account[4:]:
            raise AppError("SCOPE_MISMATCH", "Materiał pochodzi z innego konta.", 3)
        creative = ad.get("creative", {})
        hashes, videos, urls = set(), set(), []
        for obj in walk(creative):
            for key in ("image_hash", "hash"):
                if isinstance(obj.get(key), str) and re.fullmatch(r"[a-fA-F0-9]{32}", obj[key]):
                    hashes.add(obj[key])
            if obj.get("video_id"):
                videos.add(obj["video_id"])
            for key in ("image_url", "picture", "thumbnail_url"):
                if isinstance(obj.get(key), str):
                    urls.append((obj[key], "thumbnail" if key == "thumbnail_url" else "image"))
        if hashes:
            images = evidence.fetch(f"images-{ad_id}", api, args.account + "/adimages", {
                "hashes": json.dumps(sorted(hashes)), "fields": "hash,url,width,height",
            }, optional=True)
            if images:
                urls = [(i["url"], "image") for i in images if i.get("url")] + urls
        if not hashes and not videos:
            post = existing_post(evidence, api, creative)
            for obj in walk(post):
                if isinstance(obj.get("full_picture"), str):
                    urls.append((obj["full_picture"], "image"))
                if isinstance(obj.get("image"), dict) and obj["image"].get("src"):
                    urls.append((obj["image"]["src"], "image"))
        video_meta = []
        for video_id in sorted(videos):
            api.allow(video_id)
            video = evidence.fetch(f"video-{video_id}", api, video_id, {
                "fields": "id,source,length,title,description",
            }, many=False, optional=True)
            if video and video.get("id") != video_id:
                raise AppError("SCOPE_MISMATCH", "Zwrócono inne wideo.", 3)
            if video:
                video_meta.append(video_id)
                if video.get("source"):
                    urls.append((video["source"], "video"))
        assets, seen = [], set()
        for url, role in urls:
            key = hashlib.sha256(url.encode()).hexdigest()
            if key not in cached:
                try:
                    cached[key] = {"status": "available", **download(url, media_dir)}
                except AppError as exc:
                    cached[key] = {"status": "unavailable", "code": exc.code}
            asset = cached[key]
            identity = (asset.get("sha256", key), role)
            if identity in seen:
                continue
            seen.add(identity)
            if asset.get("mime") == "video/mp4" and "preparation" not in asset:
                asset["preparation"] = prepare_frames(media_dir, asset)
            assets.append({**asset, "role": role})
        cards.append({"ad_id": ad_id, "creative_id": creative.get("id"),
                      "video_ids": sorted(videos), "accessible_video_ids": video_meta,
                      "assets": assets,
                      "text_review": "pending", "visual_review": "pending"})
        # Checkpoint only cache generated by this operation; source evidence is immutable.
        temp = p / "media-downloads.tmp"
        with temp.open("w") as handle:
            json.dump(cached, handle, ensure_ascii=False, indent=2)
        temp.chmod(0o600)
        temp.replace(cache_file)
    result = {"schema_version": "1.0", "kind": "creative_media", "client_id": args.client,
              "account_id": args.account, "cards": cards, "errors": evidence.errors,
              "limitations": ["Frames do not establish motion, editing or audio quality.",
                              "No automatic content assessment has been performed."]}
    save_private(p / "media.json", result)
    return {"directory": str(args.directory.resolve()), "materials": str(p.resolve()),
            "ads": len(cards),
            "available_assets": sum(x["status"] == "available" for c in cards for x in c["assets"]),
            "errors": evidence.errors}
