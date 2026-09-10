"""Explicitly attached, portable specialist guidance; never a client document store."""

import hashlib
import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from meta_ads_manager.errors import AppError
from meta_ads_manager.meta_connection import save_private, validate_client_id
from meta_ads_manager.workspace import confined, workspace_info


def fail(message):
    raise AppError("SPECIALIST_ERROR", message, 2)


def regular(root, relative):
    path = root / relative
    if path.resolve() != path.absolute() or not path.resolve().is_relative_to(root):
        fail("Profil i jego pliki nie mogą być dowiązaniami.")
    return path


def replace_private(directory, name, data):
    target = regular(directory, name)
    temporary = directory / (".write-" + uuid4().hex + ".json")
    save_private(temporary, data)
    temporary.replace(target)


def profile_root(root):
    workspace_info(root)
    pointer = confined(root, Path("specialist.json"))
    if not pointer.exists():
        fail("Najpierw utwórz lub podłącz profil specjalisty.")
    data = json.loads(pointer.read_text())
    directory = Path(data["directory"])
    if not directory.is_absolute() or directory.resolve() != directory:
        fail("Niepoprawna ścieżka profilu.")
    profile = read_profile(directory)
    if profile["profile_id"] != data["profile_id"]:
        fail("Pod wskazaną ścieżką znajduje się inny profil.")
    return directory


def read_profile(directory):
    data = json.loads(regular(directory, "profile.json").read_text())
    if data.get("kind") != "specialist_profile" or data.get("schema_version") != "1.0":
        fail("To nie jest obsługiwany profil specjalisty.")
    validate_client_id(data["specialist_id"])
    return data


def attach(root, directory):
    workspace_info(root)
    directory = directory.expanduser().absolute()
    if directory.resolve() != directory:
        fail("Wskaż rzeczywistą ścieżkę profilu.")
    for parent in [directory, *directory.parents]:
        if (parent / "workspace.json").exists() and parent != root:
            fail("Nie podłączaj profilu przechowywanego w przestrzeni innego klienta.")
    data = read_profile(directory)
    replace_private(
        root,
        "specialist.json",
        {
            "schema_version": "1.0",
            "profile_id": data["profile_id"],
            "directory": str(directory),
        },
    )
    return {
        "specialist_id": data["specialist_id"],
        "name": data["name"],
        "profile_id": data["profile_id"],
        "directory": str(directory),
    }


def init(root, directory, identifier, name):
    workspace_info(root)
    validate_client_id(identifier)
    if not name.strip():
        fail("Podaj nazwę specjalisty.")
    directory = directory.expanduser().absolute()
    if directory.resolve() != directory or directory == root:
        fail("Wskaż osobny katalog profilu, bez dowiązań.")
    if directory.is_relative_to(root) and directory != root / "specialist":
        fail("W przestrzeni klienta profil może być tylko w specialist/.")
    for parent in [directory, *directory.parents]:
        if (parent / ".git").exists():
            fail("Profil osobisty utwórz poza repozytorium kodu.")
        if (parent / "workspace.json").exists() and parent != root:
            fail("Nie twórz profilu w przestrzeni innego klienta.")
    if directory.exists() and any(directory.iterdir()):
        fail("Katalog profilu nie jest pusty.")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    save_private(
        directory / "profile.json",
        {
            "schema_version": "1.0",
            "kind": "specialist_profile",
            "profile_id": uuid4().hex,
            "specialist_id": identifier,
            "name": name,
            "items": [],
        },
    )
    return attach(root, directory)


@contextmanager
def locked(directory):
    import fcntl

    path = regular(directory, ".profile.lock")
    with path.open("a") as handle:
        os.chmod(path, 0o600)
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fail("Inny proces aktualizuje profil; ponów później.")
        yield


def text_file(directory, row):
    path = regular(directory, row["file"])
    if not path.is_file() or path.stat().st_size > 1_000_000:
        fail("Brak pliku wytycznej lub przekroczony limit 1 MB.")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != row["sha256"]:
        fail("Plik wytycznej zmienił się; dodaj nową wersję przez specialist add --id.")
    return payload.decode("utf-8-sig")


def add(root, source, title, topic, identifier=None):
    directory = profile_root(root)
    source = source.expanduser().absolute()
    if source.is_symlink() or source.suffix.lower() not in (".md", ".txt"):
        fail("Wskaż zwykły plik Markdown lub TXT bez danych klientów.")
    if any(part in {"secrets", "config", "context", "reports", "data"} for part in source.parts):
        fail("Materiał klienta pozostaw w jego kontekście; przygotuj osobną ogólną wytyczną.")
    if source.stat().st_size > 1_000_000 or not title.strip() or not topic.strip():
        fail("Podaj tytuł, temat i plik do 1 MB.")
    payload = source.read_bytes()
    if not payload.decode("utf-8-sig").strip():
        fail("Wytyczna nie może być pusta.")
    with locked(directory):
        data = read_profile(directory)
        prior = [x for x in data["items"] if x["id"] == identifier]
        if identifier and not prior:
            fail("Nie ma wytycznej o takim ID w tym profilu.")
        identifier = identifier or "practice_" + uuid4().hex
        revision = max((r["revision"] for r in prior), default=0) + 1
        name = f"materials/{identifier}-{revision}.md"
        target = regular(directory, name)
        target.parent.mkdir(exist_ok=True, mode=0o700)
        with target.open("xb") as handle:
            os.chmod(target, 0o600)
            handle.write(payload)
        row = {
            "id": identifier,
            "revision": revision,
            "title": title,
            "topic": topic,
            "status": "draft",
            "file": name,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "created_at": datetime.now(UTC).isoformat(),
            "history": [],
        }
        data["items"].append(row)
        replace_private(directory, "profile.json", data)
        return row


def listing(root, topic=None, history=False):
    pointer = confined(root, Path("specialist.json"))
    if not pointer.exists():
        return {"attached": False, "items": []}
    directory = profile_root(root)
    data = read_profile(directory)
    rows = []
    for row in data["items"]:
        if topic is not None and row["topic"] != topic:
            continue
        if not history and row["status"] != "active":
            continue
        text_file(directory, row)
        rows.append(row)
    return {
        "attached": True,
        "profile_id": data["profile_id"],
        "specialist_id": data["specialist_id"],
        "name": data["name"],
        "items": rows,
    }


def read(root, identifier, revision=None):
    directory = profile_root(root)
    data = read_profile(directory)
    rows = [
        x
        for x in data["items"]
        if x["id"] == identifier
        and (x["revision"] == revision if revision is not None else x["status"] == "active")
    ]
    if len(rows) != 1:
        fail("Wskaż istniejącą wersję lub aktywną wytyczną.")
    return {
        "profile_id": data["profile_id"],
        "specialist_id": data["specialist_id"],
        **rows[0],
        "text": text_file(directory, rows[0]),
    }


def status(root, identifier, revision, state, reason):
    if state not in ("active", "retired") or not reason.strip():
        fail("Podaj status i rzeczywiste uzasadnienie decyzji specjalisty.")
    directory = profile_root(root)
    with locked(directory):
        data = read_profile(directory)
        row = next(
            (x for x in data["items"] if x["id"] == identifier and x["revision"] == revision), None
        )
        if row is None or row["status"] == "retired":
            fail("Wersja nie istnieje lub została wycofana. Dodaj nową wersję.")
        text_file(directory, row)
        for item in data["items"]:
            target = (
                state
                if item is row
                else (
                    "retired"
                    if state == "active" and item["id"] == identifier and item["status"] == "active"
                    else item["status"]
                )
            )
            if target != item["status"]:
                item["history"].append(
                    {
                        "previous": item["status"],
                        "status": target,
                        "reason": reason,
                        "actor": data["specialist_id"],
                        "at": datetime.now(UTC).isoformat(),
                    }
                )
                item["status"] = target
        replace_private(directory, "profile.json", data)
        return row


def add_commands(commands):
    sub = commands.add_parser("specialist").add_subparsers(dest="action", required=True)
    create = sub.add_parser("init")
    create.add_argument("--directory", type=Path, required=True)
    create.add_argument("--id", required=True)
    create.add_argument("--name", required=True)
    link = sub.add_parser("attach")
    link.add_argument("--directory", type=Path, required=True)
    add_parser = sub.add_parser("add")
    add_parser.add_argument("--file", type=Path, required=True)
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--topic", required=True)
    add_parser.add_argument("--id")
    items = sub.add_parser("list")
    items.add_argument("--topic")
    items.add_argument("--history", action="store_true")
    show = sub.add_parser("read")
    show.add_argument("--id", required=True)
    show.add_argument("--revision", type=int)
    change = sub.add_parser("status")
    change.add_argument("--id", required=True)
    change.add_argument("--revision", type=int, required=True)
    change.add_argument("--status", choices=("active", "retired"), required=True)
    change.add_argument("--reason", required=True)


def dispatch(root, args):
    if args.action == "init":
        return init(root, args.directory, args.id, args.name)
    if args.action == "attach":
        return attach(root, args.directory)
    if args.action == "add":
        return add(root, args.file, args.title, args.topic, args.id)
    if args.action == "list":
        return listing(root, args.topic, args.history)
    if args.action == "read":
        return read(root, args.id, args.revision)
    return status(root, args.id, args.revision, args.status, args.reason)
