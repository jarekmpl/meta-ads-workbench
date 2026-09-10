#!/usr/bin/env python3
"""Install a complete, separate client workspace from the reviewed release allowlist."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import venv
from pathlib import Path
from uuid import uuid4

UV_VERSION = "0.12.9"
SOURCE = Path(__file__).resolve().parent


def release_files(source):
    files = json.loads((source / "release-files.json").read_text())["files"]
    for name in files:
        path = source / name
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Niepoprawna ścieżka w wykazie wydania.")
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(source):
            raise ValueError(f"Brak zwykłego pliku wydania: {name}")
    checksum_file = source / "RELEASE-MANIFEST.json"
    if checksum_file.exists():
        expected = json.loads(checksum_file.read_text())["sha256"]
        for name in [*files, "release-files.json"]:
            actual = hashlib.sha256((source / name).read_bytes()).hexdigest()
            if expected.get(name) != actual:
                raise ValueError(f"Niezgodna suma kontrolna wydania: {name}")
    return files


def create_workspace(source, destination, client, name, agent):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", client):
        raise ValueError("Kod klienta: małe litery ASCII, cyfry i łącznik, maks. 64 znaki.")
    destination = destination.expanduser().absolute()
    if destination.is_symlink() or destination.resolve() != destination:
        raise ValueError("Wskaż rzeczywisty katalog, bez dowiązań w ścieżce.")
    if destination == source or destination.is_relative_to(source):
        raise ValueError("Katalog klienta musi być poza repozytorium instalatora.")
    for parent in [destination, *destination.parents]:
        if (parent / ".git").exists() or (parent / "workspace.json").exists():
            raise ValueError("Nie instaluj klienta wewnątrz repozytorium ani innego klienta.")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Katalog nie jest pusty. Instalator nie nadpisuje istniejącej pracy.")
    files = release_files(source)
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(destination, 0o700)
    for file in [*files, "release-files.json"]:
        target = destination / file
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / file, target)
    for directory in (
        "context/materials",
        "context/inbox",
        "projects",
        "reports",
        "output",
        "artifacts",
        "data",
        "config/local",
        "secrets",
        "tmp",
    ):
        (destination / directory).mkdir(parents=True, exist_ok=True, mode=0o700)
    info = {
        "schema_version": "1.0",
        "kind": "operator_workspace",
        "workspace_id": uuid4().hex,
        "client_id": client,
        "name": name,
        "preferred_agent": agent,
        "release_version": "0.2.0",
        "access_mode": "read_only",
    }
    path = destination / "workspace.json"
    path.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n")
    os.chmod(path, 0o600)
    # Never publish a client workspace as the tool repository, even with `git add .`.
    (destination / ".gitignore").write_text("# Cała przestrzeń klienta jest prywatna.\n*\n")
    rules = destination / ".agents/rules"
    rules.mkdir(parents=True, exist_ok=True)
    shutil.copy2(destination / "adapters/antigravity.md", rules / "meta-ads.md")
    settings = destination / ".claude"
    settings.mkdir(exist_ok=True)
    (settings / "settings.json").write_text('{"autoMemoryEnabled": false}\n')
    (destination / "context/README.md").write_text(
        "# Kontekst klienta\n\nMateriały można umieszczać w inbox/ i rejestrować przez "
        "workbench.py context add. Indeks index.json zawiera wersje i statusy. "
        "Przeczytaj docs/operator-workflow.md.\n",
        encoding="utf-8",
    )
    return destination


def install_dependencies(destination, uv_path=None):
    env = os.environ.copy()
    for name in ("UV_PROJECT_ENVIRONMENT", "VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"):
        env.pop(name, None)
    uv = uv_path or shutil.which("uv")
    if not uv:
        bootstrap = destination / ".bootstrap"
        venv.EnvBuilder(with_pip=True, symlinks=True).create(bootstrap)
        python = bootstrap / "bin/python"
        subprocess.run(
            [str(python), "-m", "pip", "install", f"uv=={UV_VERSION}"], check=True, env=env
        )
        uv = str(bootstrap / "bin/uv")
    subprocess.run(
        [str(uv), "sync", "--locked", "--python", "3.11", "--extra", "pdf", "--no-dev"],
        cwd=destination,
        check=True,
        env=env,
    )
    subprocess.run(
        [str(destination / ".venv/bin/python"), "workbench.py", "doctor"],
        cwd=destination,
        check=True,
        env=env,
    )


def main():
    parser = argparse.ArgumentParser(description="Instalator operatora Meta Ads (macOS/Linux/WSL)")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--client")
    parser.add_argument("--name")
    parser.add_argument("--agent", choices=("codex", "claude-code", "antigravity"))
    parser.add_argument("--resume", action="store_true", help="Ponów tylko instalację zależności")
    args = parser.parse_args()
    if sys.version_info < (3, 11) or os.name != "posix":
        parser.exit(2, "Wymagany Python 3.11+ i macOS/Linux/WSL. Na Windows użyj WSL.\n")
    os.umask(0o077)
    try:
        if args.resume:
            if not args.destination:
                raise ValueError("Przy --resume podaj --destination.")
            destination = args.destination.expanduser().resolve()
            info = json.loads((destination / "workspace.json").read_text())
            if info.get("kind") != "operator_workspace":
                raise ValueError("To nie jest przestrzeń operatora.")
        else:
            if not sys.stdin.isatty() and not all(
                (args.destination, args.client, args.name, args.agent)
            ):
                raise ValueError(
                    "Podaj --destination, --client, --name i --agent albo użyj terminala."
                )
            client = args.client or input("1/4. Stały kod klienta (np. klient-a): ").strip()
            name = args.name or input("2/4. Nazwa klienta: ").strip()
            agent = args.agent or input("3/4. Narzędzie (codex/claude-code/antigravity): ").strip()
            if agent not in ("codex", "claude-code", "antigravity") or not name:
                raise ValueError("Podaj nazwę klienta i jedno z trzech narzędzi.")
            suggestion = Path.home() / "MetaAds" / "clients" / client
            value = args.destination or input(f"4/4. Katalog klienta [{suggestion}]: ").strip()
            destination = Path(value) if value else suggestion
            # Resolve only the default macOS /tmp alias; caller paths must be explicit.
            destination = create_workspace(SOURCE, destination, client, name, agent)
        print("Instaluję środowisko Python i PDF. Dane dostępowe dodasz osobno.", flush=True)
        install_dependencies(destination)
        print(f"\nGotowe. Otwórz jako osobny projekt: {destination}")
        print(
            "Przeczytaj START-HERE.md. W rozmowie napisz: "
            "Przeczytaj AGENTS.md i przeprowadź mnie przez start."
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        # No credentials are accepted by this installer.
        print(f"Instalacja zatrzymana: {exc}", file=sys.stderr)
        print("Po błędzie zależności ponów z --resume --destination KATALOG.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
