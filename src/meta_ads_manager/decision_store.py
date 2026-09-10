"""Append-only, scoped local registry. No record grants Meta write authority."""

import hashlib
import json
import sqlite3
from contextlib import nullcontext
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from meta_ads_manager.decision_models import (
    BusinessGoal,
    CampaignGoalAssignment,
    Recommendation,
    RecommendationEvent,
)
from meta_ads_manager.errors import AppError


def fail(code, message):
    raise AppError(code, message, 3 if code == "SCOPE_MISMATCH" else 2)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class Decisions:
    def __init__(self, path: Path, client: str, account: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.client, self.account = client, account
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            self.db.close()
            fail("STORAGE_VERSION", "Nieobsługiwana wersja rejestru decyzji.")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS owners(account TEXT PRIMARY KEY, client TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS records(
                client TEXT NOT NULL, account TEXT NOT NULL, category TEXT NOT NULL,
                id TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY(client,account,category,id,revision));
            PRAGMA user_version=1;
        """)
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO owners VALUES (?,?)", (account, client))
            owner = self.db.execute(
                "SELECT client FROM owners WHERE account=?", (account,)
            ).fetchone()
        if owner["client"] != client:
            self.db.close()
            fail("SCOPE_MISMATCH", "Konto ma innego właściciela w rejestrze.")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.db.close()

    def scope(self, model):
        if (model.client_id, model.account_id) != (self.client, self.account):
            fail("SCOPE_MISMATCH", "Plik dotyczy innego klienta lub konta.")

    def all(self):
        rows = self.db.execute(
            "SELECT * FROM records WHERE client=? AND account=? ORDER BY category,id,revision",
            (self.client, self.account),
        ).fetchall()
        return [
            {
                "category": r["category"],
                "id": r["id"],
                "revision": r["revision"],
                "created_at": r["created_at"],
                "data": json.loads(r["payload"]),
            }
            for r in rows
        ]

    def get(self, category, identifier, revision=None):
        rows = [
            r
            for r in self.all()
            if r["category"] == category
            and r["id"] == identifier
            and (revision is None or r["revision"] == revision)
        ]
        if not rows:
            fail("NOT_FOUND", "Brak wpisu w tym zakresie klienta i konta.")
        return rows[-1]

    def _append(self, category, identifier, expected, payload):
        row = self.db.execute(
            "SELECT revision,payload FROM records WHERE client=? AND account=? AND category=? "
            "AND id=? ORDER BY revision DESC LIMIT 1",
            (self.client, self.account, category, identifier),
        ).fetchone()
        actual = row["revision"] if row else 0
        if row and row["payload"] == canonical(payload):
            return self.get(category, identifier)
        if expected != actual:
            fail("REVISION_CONFLICT", "Wpis zmienił się; odczytaj jego aktualną wersję.")
        self.db.execute(
            "INSERT INTO records VALUES (?,?,?,?,?,?,?)",
            (
                self.client,
                self.account,
                category,
                identifier,
                actual + 1,
                datetime.now(UTC).isoformat(),
                canonical(payload),
            ),
        )
        return self.get(category, identifier)

    def save_goal(self, goal: BusinessGoal):
        self.scope(goal)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            return self._append(
                "goal", goal.goal_id, goal.expected_revision, goal.model_dump(mode="json")
            )

    def assign(self, assignment: CampaignGoalAssignment):
        self.scope(assignment)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if assignment.goal_id is not None:
                self.get("goal", assignment.goal_id, assignment.goal_revision)
            previous = [
                r
                for r in self.all()
                if r["category"] == "assignment" and r["id"] == assignment.campaign_id
            ]
            if previous and assignment.effective_from < date.fromisoformat(
                previous[-1]["data"]["effective_from"]
            ):
                fail("DATE_CONFLICT", "Nowe przypisanie nie może poprzedzać ostatniego wpisu.")
            return self._append(
                "assignment",
                assignment.campaign_id,
                assignment.expected_revision,
                assignment.model_dump(mode="json"),
            )

    def add_recommendation(self, recommendation: Recommendation):
        from meta_ads_manager.workspace import context_lock

        self.scope(recommendation)
        lock = context_lock(Path.cwd()) if recommendation.context_basis else nullcontext()
        with self.db, lock:
            self.db.execute("BEGIN IMMEDIATE")
            goal = self.get("goal", recommendation.goal_id, recommendation.goal_revision)
            if recommendation.test_plan.metric == "roas" and not goal["data"]["value_action_type"]:
                fail("GOAL_INCOMPATIBLE", "Cel nie ma mapowania wartości zakupu.")
            raw = recommendation.model_dump(mode="json")
            if recommendation.followup_of:
                self.get("recommendation", recommendation.followup_of)
            fingerprint = hashlib.sha256(
                canonical(
                    {
                        "goal": [raw["goal_id"], raw["goal_revision"]],
                        "campaigns": sorted(raw["campaign_ids"]),
                        "action": " ".join(raw["action"].lower().split()),
                        "followup_of": raw["followup_of"],
                    }
                ).encode()
            ).hexdigest()
            latest = self.recommendations()
            for entry in latest:
                if entry["id"] == raw["recommendation_id"]:
                    previous = Recommendation.model_validate_json(
                        canonical(entry["data"]["definition"])
                    ).model_dump(mode="json")
                    if previous != raw:
                        fail("ID_CONFLICT", "Identyfikator rekomendacji ma inną treść.")
                    return entry
            for entry in latest:
                if entry["data"]["fingerprint"] == fingerprint:
                    return {**entry, "duplicate_of": entry["id"]}
            if recommendation.context_basis:
                from meta_ads_manager.context_engine import verify_basis

                verify_basis(Path.cwd(), recommendation.context_basis, self.client,
                             goal["data"]["project_id"])
            return self._append(
                "recommendation",
                raw["recommendation_id"],
                0,
                {
                    "definition": raw,
                    "fingerprint": fingerprint,
                    "status": "proposed",
                    "started_on": None,
                    "review_on": None,
                    "events": [],
                    "evaluation": None,
                    "meta_write_authorized": False,
                },
            )

    def recommendations(self, as_of=None, due_only=False):
        latest = {}
        for row in self.all():
            if row["category"] == "recommendation":
                latest[row["id"]] = row
        result = []
        for row in latest.values():
            data = row["data"]
            due = bool(
                data["status"] in ("running", "deferred")
                and data["review_on"]
                and date.fromisoformat(data["review_on"]) <= (as_of or date.today())
            )
            if not due_only or due:
                result.append({**row, "due": due})
        return result

    def event(self, event: RecommendationEvent):
        self.scope(event)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.get("recommendation", event.recommendation_id)
            data, raw = row["data"], event.model_dump(mode="json")
            for previous in data["events"]:
                if previous.get("event_id") == event.event_id:
                    if previous != raw:
                        fail("ID_CONFLICT", "Identyfikator zdarzenia ma inną treść.")
                    return row
            status = data["status"]
            transitions = {
                "accept": ({"proposed", "deferred"}, "accepted"),
                "reject": ({"proposed", "accepted", "deferred"}, "rejected"),
                "defer": ({"proposed", "accepted", "deferred"}, "deferred"),
                "start": ({"accepted"}, "running"),
                "cancel": ({"proposed", "accepted", "deferred", "running"}, "cancelled"),
                "note": (
                    {
                        "proposed",
                        "accepted",
                        "deferred",
                        "running",
                        "evaluated",
                        "rejected",
                        "cancelled",
                    },
                    status,
                ),
            }
            allowed, next_status = transitions[event.event]
            if status not in allowed:
                fail("INVALID_TRANSITION", "Ta decyzja nie pasuje do obecnego stanu rekomendacji.")
            if event.event == "start":
                baseline_end = date.fromisoformat(
                    data["definition"]["test_plan"]["baseline"]["until"]
                )
                if event.effective_on <= baseline_end or event.effective_on > date.today():
                    fail(
                        "DATE_CONFLICT",
                        "Start musi być po okresie bazowym i nie może być przyszły.",
                    )
                data["started_on"] = str(event.effective_on)
                data["review_on"] = str(
                    event.effective_on
                    + timedelta(days=data["definition"]["test_plan"]["evaluation_days"])
                )
            elif event.event == "defer":
                data["review_on"] = str(event.review_on)
            data["status"] = next_status
            data["events"].append(raw)
            return self._append(
                "recommendation", event.recommendation_id, event.expected_revision, data
            )

    def save_evaluation(self, identifier, expected, evaluation):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.get("recommendation", identifier)
            data = row["data"]
            if data["evaluation"] == evaluation:
                return row
            if data["status"] != "running":
                fail("INVALID_TRANSITION", "Ocenę zapisujemy dla rozpoczętego testu.")
            data["evaluation"] = evaluation
            data["status"] = "evaluated"
            data["events"].append({"event": "evaluate", "snapshot_id": evaluation["snapshot_id"]})
            return self._append("recommendation", identifier, expected, data)
