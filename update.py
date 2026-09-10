#!/usr/bin/env python3
"""Update only owned distribution files. This bootstrap uses Python's standard library."""

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from uuid import uuid4

REPO = "jarekmpl/meta-ads-workbench"
ROOT_FILES = {
    "AGENTS.md",
    "CLAUDE.md",
    "DISTRIBUTION.md",
    "README.md",
    "START-HERE.md",
    "install.py",
    "update.py",
    "workbench.py",
    "package_release.py",
    "pyproject.toml",
    "uv.lock",
    "release-files.json",
    "RELEASE-MANIFEST.json",
    ".gitignore",
}
MANAGED_DIRS = {
    "src",
    "skills",
    "knowledge",
    "docs",
    "schemas",
    "templates",
    "examples",
    "tests",
    "adapters",
}
GENERATED = ".agents/rules/meta-ads.md"
STATE = ".workbench/installed.json"
PENDING = ".workbench/pending.json"
LIMIT = 250 * 1024 * 1024


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_name(name, generated=False):
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or path.is_absolute()
        or str(path) != name
        or any(p in (".", "..") or p.startswith(".") for p in path.parts)
        or (len(path.parts) == 1 and name not in ROOT_FILES)
        or (len(path.parts) > 1 and path.parts[0] not in MANAGED_DIRS)
    ):
        if name not in ROOT_FILES and not (generated and name == GENERATED):
            raise ValueError(f"Wydanie nie może zarządzać ścieżką: {name}")
    return name


def safe_path(root, name):
    path = root / name
    if path.resolve() != path.absolute() or not path.resolve().is_relative_to(root):
        raise ValueError(f"Dowiązanie lub ścieżka poza katalogiem: {name}")
    return path


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.parent / (".write-" + uuid4().hex)
    with temporary.open("x", encoding="utf-8") as out:
        os.chmod(temporary, 0o600)
        json.dump(data, out, ensure_ascii=False, indent=2)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    temporary.replace(path)


def load(path):
    def unique(pairs):
        data = {}
        for key, value in pairs:
            if key in data:
                raise ValueError("Powtórzony klucz JSON.")
            data[key] = value
        return data

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def version(value):
    if not re.fullmatch(r"v?\d+\.\d+\.\d+", value):
        raise ValueError("Wskaż stabilne wydanie w formacie v0.6.0.")
    return tuple(int(x) for x in value.removeprefix("v").split("."))


def distribution(source):
    source = source.resolve()
    names = load(safe_path(source, "release-files.json"))["files"]
    if not isinstance(names, list) or not names or len(names) > 5000:
        raise ValueError("Niepoprawny wykaz plików.")
    all_names = [*names, "release-files.json"]
    if len({name.casefold() for name in all_names}) != len(all_names):
        raise ValueError("Powtórzone ścieżki wydania.")
    manifest = load(safe_path(source, "RELEASE-MANIFEST.json"))
    version(manifest["version"])
    if set(manifest["sha256"]) != set(all_names):
        raise ValueError("Manifest nie odpowiada wykazowi plików.")
    total = 0
    for name in all_names:
        validate_name(name)
        path = safe_path(source, name)
        if not path.is_file() or path.stat().st_size > 50 * 1024 * 1024:
            raise ValueError("Brak pliku wydania lub przekroczony limit.")
        total += path.stat().st_size
        if total > LIMIT or digest(path) != manifest["sha256"][name]:
            raise ValueError(f"Niezgodna suma kontrolna lub limit wydania: {name}")
    import tomllib

    project = tomllib.loads((source / "pyproject.toml").read_text())
    if project["project"]["version"] != manifest["version"]:
        raise ValueError("Niezgodna wersja projektu i manifestu.")
    return manifest, [name for name in all_names if name != ".gitignore"]


def incoming_files(source):
    manifest, names = distribution(source)
    mapping = {name: source / name for name in [*names, "RELEASE-MANIFEST.json"]}
    mapping[GENERATED] = source / "adapters/antigravity.md"
    return manifest["version"], mapping


def installed_state(root, source):
    """Called after a fresh installation, including generated agent entrypoints."""
    names = load(source / "release-files.json")["files"]
    owned = [n for n in names if n != ".gitignore"] + ["release-files.json", GENERATED]
    if (root / "RELEASE-MANIFEST.json").is_file():
        owned.append("RELEASE-MANIFEST.json")
    info = load(root / "workspace.json")
    return {
        "schema_version": "1.0",
        "workspace_id": info["workspace_id"],
        "version": info["release_version"],
        "python": ".venv/bin/python",
        "files": {validate_name(n, True): digest(safe_path(root, n)) for n in owned},
    }


def baseline_state(root, baseline=None):
    info = load(safe_path(root, "workspace.json"))
    if info.get("kind") != "operator_workspace" or not info.get("workspace_id"):
        raise ValueError("Wskaż zainstalowaną przestrzeń klienta.")
    state_path = safe_path(root, STATE)
    if state_path.exists():
        data = load(state_path)
        if data.get("schema_version") != "1.0" or data.get("workspace_id") != info["workspace_id"]:
            raise ValueError("Stan instalacji nie należy do tej przestrzeni.")
    else:
        if baseline is None:
            raise ValueError(
                "Starsza instalacja wymaga oryginalnego wydania przez --baseline "
                "lub pobrania go przez --github."
            )
        original_version, mapping = incoming_files(baseline)
        if original_version != info["release_version"]:
            raise ValueError("Wersja bazowa nie odpowiada pierwotnej instalacji.")
        # Releases <=0.5 did not install RELEASE-MANIFEST.json.
        mapping.pop("RELEASE-MANIFEST.json", None)
        data = {
            "schema_version": "1.0",
            "workspace_id": info["workspace_id"],
            "version": original_version,
            "python": ".venv/bin/python",
            "files": {n: digest(p) for n, p in mapping.items()},
        }
    version(data["version"])
    for name in data["files"]:
        validate_name(name, True)
    return data


def plan(root, source, baseline=None):
    if safe_path(root, PENDING).exists():
        raise ValueError("Najpierw odtwórz przerwaną aktualizację przez --rollback.")
    current = baseline_state(root, baseline)
    release, mapping = incoming_files(source)
    if version(release) < version(current["version"]):
        raise ValueError("Aktualizator nie wykonuje obniżenia wersji.")
    conflicts, changes = [], []
    for name in sorted(set(current["files"]) | set(mapping)):
        validate_name(name, True)
        path = safe_path(root, name)
        before = digest(path) if path.is_file() else None
        expected = current["files"].get(name)
        after = digest(mapping[name]) if name in mapping else None
        if (path.exists() and not path.is_file()) or before != expected:
            conflicts.append(name)
        elif before != after:
            changes.append({"path": name, "before": before, "after": after})
    return {
        "from_version": current["version"],
        "to_version": release,
        "workspace_id": current["workspace_id"],
        "conflicts": conflicts,
        "changes": changes,
        "current": current,
    }


@contextmanager
def exclusive(root):
    directory = safe_path(root, ".workbench")
    directory.mkdir(exist_ok=True, mode=0o700)
    path = safe_path(root, ".workbench/session.lock")
    with path.open("a") as handle:
        os.chmod(path, 0o600)
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError(
                "Trwa praca w przestrzeni klienta; zakończ ją przed aktualizacją."
            ) from None
        yield


def copy_atomic(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / (".update-" + uuid4().hex)
    shutil.copy2(source, temporary)
    temporary.replace(target)


def prepare_environment(root, job, uv=None):
    executable = uv or shutil.which("uv")
    if executable is None:
        candidate = root / ".bootstrap/bin/uv"
        if candidate.is_file():
            executable = str(candidate)
    if executable is None:
        raise ValueError("Zainstaluj uv albo podaj --uv ze ścieżką do programu uv.")
    env_path = safe_path(root, f".workbench/envs/{job.name}")
    env = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(name, None)
    env["UV_PROJECT_ENVIRONMENT"] = str(env_path)
    subprocess.run(
        [
            executable,
            "sync",
            "--project",
            str(job / "release"),
            "--locked",
            "--python",
            "3.11",
            "--extra",
            "pdf",
            "--no-dev",
            "--no-editable",
        ],
        env=env,
        check=True,
    )
    return str(env_path.relative_to(root) / "bin/python")


def health(root, python):
    env = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(name, None)
    # Bypass only the maintenance lock, in a short fixed-code check that performs no CLI writes.
    script = (
        "import json; from pathlib import Path; "
        "from meta_ads_manager.workspace import doctor; "
        "from meta_ads_manager import __version__; "
        'state=json.loads(Path(".workbench/installed.json").read_text()); '
        'assert __version__ == state["version"]; '
        "r=doctor(Path.cwd()); print(json.dumps(r)); "
        'raise SystemExit(0 if r["ready_local"] else 1)'
    )
    result = subprocess.run(
        [str(root / python), "-c", script],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode:
        raise ValueError("Kontrola środowiska po aktualizacji nie powiodła się.")


def rollback(root):
    pending = load(safe_path(root, PENDING))
    identifier = pending["transaction_id"]
    if not re.fullmatch(r"[0-9a-f]{32}", identifier):
        raise ValueError("Niepoprawny dziennik aktualizacji.")
    job = safe_path(root, ".workbench/updates/" + identifier)
    journal = load(safe_path(job, "journal.json"))
    info = load(root / "workspace.json")
    if journal["workspace_id"] != info["workspace_id"]:
        raise ValueError("Kopia należy do innej przestrzeni.")
    for item in journal["entries"]:
        name = item["path"]
        if name != STATE:
            validate_name(name, True)
        target = safe_path(root, name)
        actual = digest(target) if target.is_file() else None
        if actual not in (item["before"], item["after"]):
            raise ValueError(f"Plik zmieniono po rozpoczęciu aktualizacji: {name}")
        if item["before"] is not None:
            backup = safe_path(job / "backup", name)
            if not backup.is_file() or digest(backup) != item["before"]:
                raise ValueError("Kopia plików narzędzia jest niekompletna.")
    for item in reversed(journal["entries"]):
        target = safe_path(root, item["path"])
        if item["before"] is None:
            if target.exists():
                target.unlink()
        else:
            copy_atomic(job / "backup" / item["path"], target)
    save(job / "result.json", {"status": "rolled_back"})
    safe_path(root, PENDING).unlink()
    return {"status": "rolled_back", "transaction_id": identifier}


def apply(root, source, baseline=None, uv=None, prepare=prepare_environment, check=health):
    with exclusive(root):
        if safe_path(root, PENDING).exists():
            raise ValueError("Najpierw uruchom update.py --rollback dla przerwanej aktualizacji.")
        proposed = plan(root, source, baseline)
        if proposed["conflicts"]:
            raise ValueError("Lokalne zmiany lub obce pliki: " + ", ".join(proposed["conflicts"]))
        if not proposed["changes"] and proposed["from_version"] == proposed["to_version"]:
            return {"status": "up_to_date", "version": proposed["to_version"]}
        identifier = uuid4().hex
        job = safe_path(root, ".workbench/updates/" + identifier)
        job.mkdir(parents=True, mode=0o700)
        _, mapping = incoming_files(source)
        # Stage only validated files, never arbitrary files adjacent to the release.
        stage = job / "release"
        for name, original in mapping.items():
            if name != GENERATED:
                copy_atomic(original, stage / name)
        copy_atomic(source / ".gitignore", stage / ".gitignore")
        distribution(stage)
        python = prepare(root, job, uv)
        # Recheck after downloads/builds so concurrent manual edits cannot be overwritten.
        fresh = plan(root, stage, baseline)
        if fresh != proposed:
            raise ValueError("Stan plików zmienił się podczas przygotowania aktualizacji.")
        _, mapping = incoming_files(stage)
        state = {
            "schema_version": "1.0",
            "workspace_id": proposed["workspace_id"],
            "version": proposed["to_version"],
            "python": python,
            "files": {n: digest(p) for n, p in mapping.items()},
        }
        save(job / "next-state.json", state)
        entries = [
            *proposed["changes"],
            {
                "path": STATE,
                "before": digest(root / STATE) if (root / STATE).is_file() else None,
                "after": digest(job / "next-state.json"),
            },
        ]
        for item in entries:
            if item["before"] is not None:
                copy_atomic(safe_path(root, item["path"]), job / "backup" / item["path"])
        save(job / "journal.json", {"workspace_id": proposed["workspace_id"], "entries": entries})
        save(root / PENDING, {"transaction_id": identifier})
        try:
            for item in entries:
                target = safe_path(root, item["path"])
                actual = digest(target) if target.is_file() else None
                if actual != item["before"]:
                    raise ValueError("Wykryto równoległą zmianę pliku.")
                if item["after"] is None:
                    target.unlink()
                else:
                    original = (
                        job / "next-state.json" if item["path"] == STATE else mapping[item["path"]]
                    )
                    copy_atomic(original, target)
            check(root, python)
            save(job / "result.json", {"status": "updated", "version": proposed["to_version"]})
            safe_path(root, PENDING).unlink()
        except Exception:
            rollback(root)
            raise
        return {
            "status": "updated",
            "version": proposed["to_version"],
            "transaction_id": identifier,
            "files_changed": len(proposed["changes"]),
            "python": python,
        }


def unpack(archive, checksum, destination):
    if archive.stat().st_size > LIMIT:
        raise ValueError("Archiwum przekracza limit rozmiaru.")
    fields = checksum.read_text().strip().split()
    if len(fields) != 2 or fields[1] != archive.name or fields[0] != digest(archive):
        raise ValueError("Niezgodna suma kontrolna pobranej paczki.")
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        names, total = set(), 0
        if len(entries) > 5000:
            raise ValueError("Zbyt wiele plików w paczce.")
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if entry.is_dir():
                continue
            if len(path.parts) < 2 or path.parts[0] != "meta-ads-workbench":
                raise ValueError("Niepoprawny katalog główny archiwum.")
            relative = str(PurePosixPath(*path.parts[1:]))
            validate_name(relative)
            if entry.filename != "meta-ads-workbench/" + relative:
                raise ValueError("Niepoprawna ścieżka archiwum.")
            if relative.casefold() in names or stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("Powtórzona ścieżka lub dowiązanie w archiwum.")
            names.add(relative.casefold())
            total += entry.file_size
            if total > LIMIT or entry.file_size > 50 * 1024 * 1024:
                raise ValueError("Rozpakowane wydanie przekracza limit.")
            target = safe_path(destination, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(entry) as inp, target.open("xb") as out:
                shutil.copyfileobj(inp, out)
    distribution(destination)
    return destination


def github_release(directory, tag=None, gh="gh"):
    if tag is not None:
        version(tag)
    command = [
        gh,
        "release",
        "view",
        *([tag] if tag else []),
        "--repo",
        REPO,
        "--json",
        "tagName,isDraft,isPrerelease",
    ]
    metadata = json.loads(subprocess.check_output(command, text=True, timeout=60))
    actual = metadata["tagName"]
    version(actual)
    if metadata["isDraft"] or metadata["isPrerelease"] or (tag and actual != tag):
        raise ValueError("Wskaż opublikowane stabilne wydanie.")
    directory.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            gh,
            "release",
            "download",
            actual,
            "--repo",
            REPO,
            "--dir",
            str(directory),
            "--pattern",
            "meta-ads-workbench.zip",
            "--pattern",
            "meta-ads-workbench.zip.sha256",
        ],
        check=True,
        timeout=180,
    )
    result = unpack(
        directory / "meta-ads-workbench.zip",
        directory / "meta-ads-workbench.zip.sha256",
        directory / "release",
    )
    if version(distribution(result)[0]["version"]) != version(actual):
        raise ValueError("Tag i wersja paczki są różne.")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Aktualizacja kodu bez nadpisywania danych klienta"
    )
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parent)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--source", type=Path)
    source.add_argument("--github", action="store_true")
    parser.add_argument("--version")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--gh", default="gh")
    parser.add_argument("--uv")
    args = parser.parse_args(argv)
    try:
        root = args.workspace.expanduser().absolute()
        if root.resolve() != root:
            raise ValueError("Wskaż rzeczywistą ścieżkę przestrzeni klienta.")
        if not (root / "workspace.json").is_file():
            raise ValueError("Brak zainstalowanej przestrzeni klienta.")
        if args.rollback:
            with exclusive(root):
                result = rollback(root)
        else:
            if not (args.source or args.github) or (args.version and not args.github):
                raise ValueError("Wskaż --source KATALOG albo --github [--version vX.Y.Z].")
            with tempfile.TemporaryDirectory(prefix="meta-ads-update-") as temporary:
                folder = Path(temporary).resolve()
                candidate = (
                    github_release(folder / "new", args.version, args.gh)
                    if args.github
                    else args.source.expanduser().resolve()
                )
                baseline = args.baseline.expanduser().resolve() if args.baseline else None
                if not (root / STATE).exists() and baseline is None and args.github:
                    old = load(root / "workspace.json")["release_version"]
                    baseline = github_release(folder / "old", "v" + old, args.gh)
                if args.apply:
                    result = apply(root, candidate, baseline, args.uv)
                else:
                    with exclusive(root):
                        result = plan(root, candidate, baseline)
                        result.pop("current")
                        result["status"] = "blocked" if result["conflicts"] else "ready"
        print(json.dumps({"ok": True, "data": result}, ensure_ascii=False))
        return 2 if result.get("status") == "blocked" else 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        # subprocess failures may contain command paths, never credential values.
        message = str(exc) if isinstance(exc, ValueError) else "Sprawdź pliki, dostęp i narzędzia."
        print(
            json.dumps(
                {"ok": False, "error": {"code": "UPDATE_FAILED", "message": message}},
                ensure_ascii=False,
            )
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
