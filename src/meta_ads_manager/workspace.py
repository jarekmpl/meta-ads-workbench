"""Client-scoped operator workspaces. Local files only; no account mutations."""

import argparse
import hashlib
import json
import os
import sys
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from meta_ads_manager.errors import AppError
from meta_ads_manager.meta_connection import (
    Connection,
    config_path,
    connection_status,
    save_private,
    validate_client_id,
)
from meta_ads_manager.workspace_lock import session

MANIFEST = "workspace.json"
DATA_ROOTS = {"data", "reports", "output", "artifacts", "tmp", "context", "projects"}
PRIVATE_ROOTS = {"secrets", "config", ".git", ".venv", ".bootstrap"}


def workspace_info(root: Path, *, required: bool = True) -> dict | None:
    path = root / MANIFEST
    if not path.exists():
        if required:
            raise AppError("WORKSPACE_REQUIRED", "Otwórz katalog zainstalowanego klienta.", 2)
        return None
    if path.is_symlink():
        raise AppError("WORKSPACE_INVALID", "Manifest nie może być dowiązaniem.", 2)
    info = json.loads(path.read_text(encoding="utf-8"))
    if info.get("schema_version") != "1.0" or info.get("kind") != "operator_workspace":
        raise AppError("WORKSPACE_INVALID", "Nieobsługiwany manifest przestrzeni.", 2)
    validate_client_id(info.get("client_id", ""))
    return info


def confined(root: Path, path: Path, *, output: bool = False) -> Path:
    resolved = (root / path).resolve()
    try:
        relative = resolved.relative_to(root.resolve())
    except ValueError:
        raise AppError("SCOPE_MISMATCH", "Ścieżka wychodzi poza katalog klienta.", 3) from None
    if not relative.parts or relative.parts[0] in PRIVATE_ROOTS:
        raise AppError("SCOPE_MISMATCH", "Niedozwolona ścieżka danych.", 3)
    if output and relative.parts[0] not in DATA_ROOTS:
        raise AppError("SCOPE_MISMATCH", "Wynik zapisz w katalogu danych tego klienta.", 3)
    return resolved


def guard_cli(args, root: Path) -> None:
    """Protect installed workspaces; preserve the development CLI contract."""
    info = workspace_info(root, required=False)
    if info is None:
        if any((parent / MANIFEST).exists() for parent in root.parents):
            raise AppError("WORKSPACE_ROOT_REQUIRED", "Uruchom komendę w katalogu klienta.", 2)
        return
    if args.demo:
        raise AppError("SCOPE_MISMATCH", "Demo uruchamiaj poza przestrzenią klienta.", 3)
    if getattr(args, "client", None) not in (None, info["client_id"]):
        raise AppError("SCOPE_MISMATCH", "Polecenie dotyczy innego klienta.", 3)
    for folder in DATA_ROOTS | {"config", "secrets"}:
        if (root / folder).resolve() != root.resolve() / folder:
            raise AppError("SCOPE_MISMATCH", "Katalog klienta jest dowiązaniem.", 3)
    local_config = root / "config" / "local"
    if local_config.resolve() != root.resolve() / "config" / "local":
        raise AppError("SCOPE_MISMATCH", "Katalog konfiguracji jest dowiązaniem.", 3)
    for path in local_config.glob("meta-*.json"):
        if path.name != f"meta-{info['client_id']}.json" or path.is_symlink():
            raise AppError("SCOPE_MISMATCH", "Obca konfiguracja w przestrzeni klienta.", 3)
    for attr in ("file", "input", "notes", "assessment", "directory", "pdf", "output", "preview"):
        value = getattr(args, attr, None)
        if value is not None:
            confined(root, value, output=attr in ("output", "directory", "pdf", "preview"))
    if args.data_dir.resolve() != (root / "data").resolve():
        raise AppError("SCOPE_MISMATCH", "Baza klienta musi znajdować się w jego data/.", 3)
    for db in (root / "data").glob("*.sqlite*"):
        confined(root, db, output=True)
    path = config_path(root, info["client_id"])
    account = getattr(args, "account", None)
    if path.exists():
        connection = Connection.model_validate_json(path.read_text())
        if connection.client_id != info["client_id"] or (
            account and connection.account_id and connection.account_id != account
        ):
            raise AppError("SCOPE_MISMATCH", "Konto nie należy do tej konfiguracji.", 3)


@contextmanager
def context_lock(root: Path):
    directory = confined(root, Path("context"), output=True)
    directory.mkdir(exist_ok=True, mode=0o700)
    lock = directory / ".write.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise AppError("CONTEXT_BUSY", "Inny proces zapisuje kontekst; ponów później.", 2) from None
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def context_index(root: Path) -> dict:
    info = workspace_info(root)
    path = confined(root, Path("context/index.json"))
    if not path.exists():
        return {"schema_version": "1.0", "client_id": info["client_id"], "items": []}
    index = json.loads(path.read_text())
    if index.get("client_id") != info["client_id"] or index.get("schema_version") != "1.0":
        raise AppError("SCOPE_MISMATCH", "Indeks kontekstu należy do innego klienta.", 3)
    return index


def save_index(root: Path, index: dict) -> None:
    temporary = root / "context" / f".index-{uuid4().hex}.json"
    save_private(temporary, index)
    temporary.replace(root / "context" / "index.json")


def add_context(root: Path, args) -> dict:
    workspace_info(root)
    source = args.file.expanduser().absolute()
    if source.is_symlink() or not source.is_file():
        raise AppError("CONTEXT_FILE", "Wskaż zwykły plik z kontekstem klienta.", 2)
    if any(part in PRIVATE_ROOTS for part in source.resolve().parts):
        raise AppError("CONTEXT_FILE", "Nie importuj poświadczeń ani konfiguracji.", 2)
    if source.stat().st_size > 50 * 1024 * 1024:
        raise AppError("CONTEXT_FILE", "Limit jednego materiału wynosi 50 MB.", 2)
    if args.valid_until:
        args.valid_until = date.fromisoformat(args.valid_until).isoformat()
    valid_from = getattr(args, "valid_from", None)
    document_date = getattr(args, "document_date", None)
    version_of = getattr(args, "version_of", None)
    valid_from = date.fromisoformat(valid_from).isoformat() if valid_from else None
    document_date = date.fromisoformat(document_date).isoformat() if document_date else None
    if valid_from and args.valid_until and valid_from > args.valid_until:
        raise AppError("CONTEXT_DATES", "Początek ważności jest późniejszy od końca.", 2)
    with context_lock(root):
        index = context_index(root)
        if version_of:
            previous = next((x for x in index["items"] if x["id"] == version_of), None)
            if previous is None or previous.get("project") != args.project:
                raise AppError("SCOPE_MISMATCH", "Brak poprzedniej wersji w tym projekcie.", 3)
        material_id = "ctx_" + uuid4().hex
        suffix = source.suffix.lower()
        allowed = ".abcdefghijklmnopqrstuvwxyz0123456789"
        if len(suffix) > 12 or any(c not in allowed for c in suffix):
            suffix = ".bin"
        relative = Path("context/materials") / f"{material_id}{suffix}"
        target = confined(root, relative, output=True)
        target.parent.mkdir(exist_ok=True, mode=0o700)
        payload = source.read_bytes()
        with target.open("xb") as handle:
            os.chmod(target, 0o600)
            handle.write(payload)
        item = {
            "id": material_id,
            "title": args.title,
            "type": args.type,
            "project": args.project,
            "tags": args.tag,
            "status": "draft",
            "valid_until": args.valid_until,
            "valid_from": valid_from,
            "document_date": document_date,
            "version_of": version_of,
            "added_at": datetime.now(UTC).isoformat(),
            "file": relative.as_posix(),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "history": [],
        }
        index["items"].append(item)
        save_index(root, index)
        return item


def context_items(root: Path) -> dict:
    index = context_index(root)
    for item in index["items"]:
        path = confined(root, Path(item["file"]))
        intact = path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
        item["integrity"] = "ok" if intact else "changed_or_missing"
        item["expired"] = bool(
            item.get("valid_until") and date.fromisoformat(item["valid_until"]) < date.today()
        )
    return index


def set_context_status(root: Path, args) -> dict:
    with context_lock(root):
        index = context_index(root)
        item = next((item for item in index["items"] if item["id"] == args.id), None)
        if item is None:
            raise AppError("CONTEXT_NOT_FOUND", "Brak wskazanego materiału.", 2)
        path = confined(root, Path(item["file"]))
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise AppError("CONTEXT_CHANGED", "Materiał zmienił się; zaimportuj nową wersję.", 2)
        item["history"].append(
            {
                "previous": item["status"],
                "status": args.status,
                "reason": args.reason,
                "at": datetime.now(UTC).isoformat(),
            }
        )
        item["status"] = args.status
        save_index(root, index)
        return item


def doctor(root: Path) -> dict:
    info = workspace_info(root)
    checks = {
        "workspace": True,
        "python": sys.version_info >= (3, 11),
        "local_engine": Path(__file__).resolve().is_relative_to(root.resolve()),
    }
    for module in ("pydantic", "reportlab", "pypdf", "pypdfium2"):
        try:
            __import__(module)
            checks[module] = True
        except ImportError:
            checks[module] = False
    for file in ("AGENTS.md", "CLAUDE.md", "skills/miodkuj/SKILL.md"):
        checks[file] = (root / file).is_file()
    status = (
        connection_status(root, info["client_id"])
        if config_path(root, info["client_id"]).exists()
        else {"status": "NOT_CONFIGURED"}
    )
    return {
        "client_id": info["client_id"],
        "checks": checks,
        "connection": status,
        "ready_local": all(checks.values()),
        "writes": status.get("configuration", {}).get("access_mode") == "approved_create_paused",
    }


def onboard(root: Path) -> dict:
    info = workspace_info(root)
    client = info["client_id"]
    if not sys.stdin.isatty():
        raise AppError("INTERACTIVE_REQUIRED", "Kreator uruchom w lokalnym terminalu.", 2)
    print(f"Konfiguracja klienta: {info['name']} ({client}). Dostęp tylko do odczytu.")
    if config_path(root, client).exists():
        print("Konfiguracja już istnieje; nie zmieniam jej.")
        return connection_status(root, client)
    account = input("Numer konta reklamowego (z act_ lub bez): ").strip().removeprefix("act_")
    connection = Connection(
        client_id=client,
        account_id="act_" + account,
        app_id=input("ID aplikacji Meta: ").strip(),
        api_version=input("Wersja API z panelu aplikacji (np. vNN.N): ").strip(),
        business_id=input("ID portfolio (opcjonalnie, Enter pomija): ").strip() or None,
    )
    save_private(config_path(root, client), connection.model_dump(mode="json"))
    print(f"Wpisz token: python3 workbench.py meta auth store-token --client {client}")
    print("Następnie poproś agenta o test połączenia. Nie wklejaj tokena do rozmowy.")
    return connection_status(root, client)


def parser() -> argparse.ArgumentParser:
    from meta_ads_manager.context_cli import add_commands

    root = argparse.ArgumentParser(description="Przestrzeń operatora jednego klienta")
    sub = root.add_subparsers(dest="command", required=True)
    from meta_ads_manager.specialist import add_commands as specialist_commands

    specialist_commands(sub)
    for command in ("doctor", "status", "onboard"):
        sub.add_parser(command)
    meta = sub.add_parser("meta", help="Przekaż pozostałe argumenty do meta-ads")
    meta.add_argument("args", nargs=argparse.REMAINDER)
    context = sub.add_parser("context").add_subparsers(dest="action", required=True)
    context.add_parser("list")
    add = context.add_parser("add")
    add.add_argument("--file", type=Path, required=True)
    add.add_argument("--title", required=True)
    add.add_argument("--type", default="note", help="Dowolny rodzaj materiału")
    add.add_argument("--project")
    add.add_argument("--tag", action="append", default=[])
    add.add_argument("--valid-until")
    add.add_argument("--valid-from")
    add.add_argument("--document-date", help="Data dokumentu lub spotkania, YYYY-MM-DD")
    add.add_argument("--version-of", help="ID poprzedniej wersji; bez zmiany jej statusu")
    state = context.add_parser("status")
    state.add_argument("--id", required=True)
    state.add_argument("--status", choices=("draft", "confirmed", "superseded"), required=True)
    state.add_argument("--reason", required=True)
    add_commands(context)
    return root


@session
def run(argv: list[str] | None = None) -> int:
    from meta_ads_manager.cli import run as meta_run

    try:
        root = Path.cwd()
        workspace_info(root)
        arguments = sys.argv[1:] if argv is None else argv
        if arguments[:1] == ["meta"]:
            return meta_run(arguments[1:])
        args = parser().parse_args(arguments)
        if args.command == "meta":
            return meta_run(args.args)
        guard_cli(argparse.Namespace(demo=False, data_dir=root / "data"), root)
        output = getattr(args, "output", None)
        if output:
            output = confined(root, output, output=True)
            # Derived exports must not overwrite source materials or either registry.
            if output.is_relative_to((root / "context").resolve()):
                raise AppError("CONTEXT_OUTPUT", "Eksport zapisz w output/ lub reports/.", 2)
            if output.exists():
                raise AppError("CONTEXT_OUTPUT", "Wybierz nową nazwę pliku eksportu.", 2)
        if args.command == "doctor":
            result = doctor(root)
        elif args.command == "status":
            result = workspace_info(root)
        elif args.command == "onboard":
            result = onboard(root)
        elif args.command == "specialist":
            from meta_ads_manager.specialist import dispatch as specialist_dispatch

            result = specialist_dispatch(root, args)
        elif args.action == "add":
            result = add_context(root, args)
        elif args.action == "status":
            result = set_context_status(root, args)
        elif args.action == "list":
            result = context_items(root)
        else:
            from meta_ads_manager.context_cli import dispatch

            result = dispatch(root, args)
        if output:
            save_private(output, result)
        print(json.dumps({"ok": True, "data": result}, ensure_ascii=False))
        return 1 if args.command == "doctor" and not result["ready_local"] else 0
    except AppError as exc:
        print(json.dumps({"ok": False, "error": exc.as_dict()}, ensure_ascii=False))
        return exc.exit_code
    except (OSError, ValueError, KeyError, TypeError):
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "WORKSPACE_ERROR",
                        "message": "Sprawdź plik, format i uprawnienia przestrzeni klienta.",
                    },
                }
            )
        )
        return 2


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
