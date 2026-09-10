"""Coordinate workspace CLI sessions with the standalone updater (POSIX)."""

import fcntl
import json
import os
from functools import wraps
from pathlib import Path


def session(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        root = Path.cwd().resolve()
        if not (root / "workspace.json").exists():
            return function(*args, **kwargs)
        directory = root / ".workbench"
        if directory.resolve() != directory:
            return blocked()
        directory.mkdir(exist_ok=True, mode=0o700)
        lock = directory / "session.lock"
        if lock.resolve() != lock:
            return blocked()
        with lock.open("a") as handle:
            os.chmod(lock, 0o600)
            try:
                fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                return blocked()
            if (directory / "pending.json").exists():
                return blocked()
            return function(*args, **kwargs)

    return guarded


def blocked():
    print(
        json.dumps(
            {
                "ok": False,
                "error": {
                    "code": "WORKSPACE_MAINTENANCE",
                    "message": (
                        "Trwa aktualizacja albo czeka na odtworzenie. Sprawdź update.py --rollback."
                    ),
                },
            },
            ensure_ascii=False,
        )
    )
    return 2
