#!/usr/bin/env python3
"""Export only explicitly reviewed files, never a recursive copy of the working directory."""

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

from install import release_files

FORBIDDEN = {
    "reports",
    "output",
    "data",
    "secrets",
    "tmp",
    "config",
    "context",
    "projects",
    ".git",
    ".venv",
    "__pycache__",
    "dist",
    "reviews",
    "specialist",
    "specialists",
    ".workbench",
}
PATTERNS = [
    rb"EAA[A-Za-z0-9]{40,}",
    rb"gh[pousr]_[A-Za-z0-9]{30,}",
    rb"github_pat_[A-Za-z0-9_]{30,}",
    rb"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    rb"/Users/[A-Za-z0-9_]+/",
    rb"act_[0-9]{8,}",
]


def check_files(root, files):
    findings = []
    for name in files:
        path = Path(name)
        if path.name in ("specialist.json", "profile.json", "workspace.json"):
            findings.append(f"Prywatny plik: {name}")
            continue
        if any(part in FORBIDDEN for part in path.parts) or path.name == "language-review.json":
            findings.append(f"Niedozwolony plik: {name}")
            continue
        payload = (root / name).read_bytes()
        # Scanner patterns themselves are code, not credentials. Binary branded assets are allowed.
        if path.suffix not in (".png", ".ttf") and name != "package_release.py":
            if any(re.search(pattern, payload) for pattern in PATTERNS):
                findings.append(f"Potencjalne dane prywatne: {name}")
    if findings:
        raise ValueError("\n".join(findings))


def build(source, destination):
    files = release_files(source)
    check_files(source, files)
    if destination.exists():
        raise ValueError("Katalog wydania już istnieje; wybierz nowy.")
    destination.mkdir(parents=True)
    hashes = {}
    for name in [*files, "release-files.json"]:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)
        hashes[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    (destination / "RELEASE-MANIFEST.json").write_text(
        json.dumps({"version": "0.6.1", "sha256": hashes}, indent=2) + "\n"
    )
    archive = destination.parent / (destination.name + ".zip")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as out:
        for file in sorted(destination.rglob("*")):
            if file.is_file():
                out.write(file, Path(destination.name) / file.relative_to(destination))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{checksum}  {archive.name}\n")
    return {
        "directory": str(destination),
        "archive": str(archive),
        "sha256": checksum,
        "file_count": len(hashes) + 1,
    }


def main():
    parser = argparse.ArgumentParser(description="Przygotuj czystą paczkę do publikacji")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    try:
        if args.check:
            files = release_files(root)
            check_files(root, files)
            print(json.dumps({"ok": True, "files": len(files)}))
        elif args.destination:
            print(json.dumps(build(root, args.destination.resolve())))
        else:
            parser.error("Podaj --destination lub --check")
    except (ValueError, OSError) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
