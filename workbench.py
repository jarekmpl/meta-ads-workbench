#!/usr/bin/env python3
"""Run the installed client environment regardless of the caller's working directory."""

import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
python = root / ".venv/bin/python"
if not (root / "workspace.json").is_file() or not python.is_file():
    sys.exit("Najpierw zainstaluj osobną przestrzeń klienta przez install.py.")
os.chdir(root)
os.umask(0o077)
for name in ("PYTHONPATH", "PYTHONHOME"):
    os.environ.pop(name, None)
os.execv(str(python), [str(python), "-m", "meta_ads_manager.workspace", *sys.argv[1:]])
