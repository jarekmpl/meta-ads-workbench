#!/usr/bin/env python3
"""Run the installed client environment regardless of the caller's working directory."""

import json
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
if (root / ".workbench/pending.json").exists():
    sys.exit("Przerwana aktualizacja: uruchom update.py --rollback z kompletnej paczki.")
python = root / ".venv/bin/python"
state = root / ".workbench/installed.json"
if state.exists():
    if state.resolve() != state:
        sys.exit("Niepoprawna ścieżka stanu instalacji.")
    selected = json.loads(state.read_text())["python"]
    candidate = root / selected
    if candidate.parent.resolve() != candidate.parent or not (
        selected == ".venv/bin/python"
        or (
            selected.startswith(".workbench/envs/")
            and selected.endswith("/bin/python")
            and ".." not in Path(selected).parts
        )
    ):
        sys.exit("Niepoprawna ścieżka środowiska Python.")
    python = candidate
if not (root / "workspace.json").is_file() or not python.is_file():
    sys.exit("Najpierw zainstaluj osobną przestrzeń klienta przez install.py.")
os.chdir(root)
os.umask(0o077)
for name in ("PYTHONPATH", "PYTHONHOME"):
    os.environ.pop(name, None)
os.execv(str(python), [str(python), "-m", "meta_ads_manager.workspace", *sys.argv[1:]])
