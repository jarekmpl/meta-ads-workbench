"""Scoped, append-only snapshots and reports in a local SQLite database."""

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from meta_ads_manager.errors import AppError
from meta_ads_manager.models import Snapshot


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            self.connection.close()
            raise AppError("STORAGE_VERSION", "Nieobsługiwana wersja bazy danych.", 1)
        if version == 0:
            self.connection.executescript("""
                BEGIN;
                CREATE TABLE accounts (
                    account_id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    UNIQUE(client_id, account_id)
                );
                CREATE TABLE snapshots (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT UNIQUE NOT NULL,
                    client_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    UNIQUE(run_id, client_id, account_id),
                    FOREIGN KEY(client_id, account_id)
                        REFERENCES accounts(client_id, account_id)
                );
                CREATE INDEX snapshots_scope ON snapshots(client_id, account_id, sequence);
                CREATE TABLE reports (
                    run_id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    snapshot_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    FOREIGN KEY(snapshot_id, client_id, account_id)
                        REFERENCES snapshots(run_id, client_id, account_id)
                );
                PRAGMA user_version = 1;
                COMMIT;
            """)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.connection.close()

    def save_snapshot(self, snapshot: Snapshot) -> dict:
        run_id = f"sync_{uuid4().hex}"
        payload = snapshot.model_dump_json()
        digest = hashlib.sha256(payload.encode()).hexdigest()
        with self.connection:
            owner = self.connection.execute(
                "SELECT client_id FROM accounts WHERE account_id = ?", (snapshot.account_id,)
            ).fetchone()
            if owner is not None and owner["client_id"] != snapshot.client_id:
                raise AppError("SCOPE_MISMATCH", "Konto ma już innego właściciela w bazie.", 3)
            self.connection.execute(
                "INSERT OR IGNORE INTO accounts VALUES (?, ?)",
                (snapshot.account_id, snapshot.client_id),
            )
            self.connection.execute(
                """INSERT INTO snapshots
                   (run_id, client_id, account_id, created_at, content_hash, payload)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    snapshot.client_id,
                    snapshot.account_id,
                    datetime.now(UTC).isoformat(),
                    digest,
                    payload,
                ),
            )
        return {
            "run_id": run_id,
            "status": "SUCCEEDED",
            "source": snapshot.source,
            "since": snapshot.since.isoformat(),
            "until": snapshot.until.isoformat(),
            "fact_count": len(snapshot.facts),
            "content_hash": digest,
        }

    def snapshot(
        self, client: str, account: str, run_id: str | None = None
    ) -> tuple[str, Snapshot]:
        query = "SELECT run_id, payload FROM snapshots WHERE client_id = ? AND account_id = ?"
        args = [client, account]
        if run_id:
            query += " AND run_id = ?"
            args.append(run_id)
        row = self.connection.execute(query + " ORDER BY sequence DESC LIMIT 1", args).fetchone()
        if row is None:
            raise AppError("INSUFFICIENT_DATA", "Brak snapshotu w tym zakresie; wykonaj sync.", 6)
        return row["run_id"], Snapshot.model_validate_json(row["payload"])

    def save_report(self, report: dict) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO reports VALUES (?, ?, ?, ?, ?)",
                (
                    report["run_id"],
                    report["client_id"],
                    report["account_id"],
                    report["snapshot_id"],
                    json.dumps(report, ensure_ascii=False, allow_nan=False),
                ),
            )

    def report(self, client: str, account: str, run_id: str) -> dict:
        row = self.connection.execute(
            "SELECT payload FROM reports WHERE client_id = ? AND account_id = ? AND run_id = ?",
            (client, account, run_id),
        ).fetchone()
        if row is None:
            raise AppError("INSUFFICIENT_DATA", "Brak raportu w wybranym zakresie.", 6)
        return json.loads(row["payload"])
