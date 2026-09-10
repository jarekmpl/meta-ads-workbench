"""Durable draft versions, account counters, plans, approvals and execution receipts."""

from datetime import UTC, datetime
from uuid import uuid4

from meta_ads_manager.campaign_planner import DEPENDENCIES, EDITABLE, TECHNICAL, readiness
from meta_ads_manager.decision_store import Decisions, fail


class WizardStore(Decisions):
    def start(self, project, identifier=None):
        identifier = identifier or "draft-" + uuid4().hex
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            return self._append(
                "draft",
                identifier,
                0,
                {
                    "client_id": self.client,
                    "account_id": self.account,
                    "project_id": project,
                    "fields": {},
                    "website_evidence": [],
                    "resource_evidence": [],
                },
            )

    def answer(self, answer):
        self.scope(answer)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.get("draft", answer.draft_id)
            if row["revision"] != answer.expected_revision:
                fail("REVISION_CONFLICT", "Brief zmienił się; odczytaj aktualną wersję.")
            data = row["data"]
            unknown = set(answer.fields) - EDITABLE
            if unknown:
                fail("BRIEF_FIELD", "Nieobsługiwane pole briefu: " + ", ".join(sorted(unknown)))
            invalidated = set()
            for key, value in answer.fields.items():
                if value.source == "api" and key not in TECHNICAL:
                    fail("BRIEF_CONFIRMATION", "Wyboru i treści nie może potwierdzić odczyt API.")
                old = data["fields"].get(key)
                if old and old["value"] != value.value:
                    invalidated |= DEPENDENCIES.get(key, set())
            pending = list(invalidated)
            while pending:
                key = pending.pop()
                new = DEPENDENCIES.get(key, set()) - invalidated
                invalidated |= new
                pending.extend(new)
            for key in invalidated - set(answer.fields):
                if key in data["fields"]:
                    data["fields"][key]["state"] = "conflict"
            for key, value in answer.fields.items():
                data["fields"][key] = {
                    **value.model_dump(mode="json"),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            return self._append("draft", answer.draft_id, row["revision"], data)

    def evidence(self, identifier, revision, kind, payload):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.get("draft", identifier)
            if row["revision"] != revision:
                fail("REVISION_CONFLICT", "Brief zmienił się podczas pobierania.")
            row["data"][kind].append(payload)
            if kind == "resource_evidence":
                for field, api_key in (("currency", "currency"), ("timezone", "timezone_name")):
                    value = payload.get("account", {}).get(api_key)
                    if not isinstance(value, str) or not value:
                        continue
                    previous = row["data"]["fields"].get(field)
                    if previous and previous["value"] != value:
                        previous["state"] = "conflict"
                    elif previous is None:
                        row["data"]["fields"][field] = {
                            "value": value,
                            "state": "confirmed",
                            "source": "api",
                            "evidence_ref": f"resource_evidence:{len(row['data'][kind])}",
                            "updated_at": datetime.now(UTC).isoformat(),
                        }
            return self._append("draft", identifier, revision, row["data"])

    def reserve(self, draft_id, revision, brief):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            identifier = f"{draft_id}:{revision}"
            existing = [
                r for r in self.all() if r["category"] == "reservation" and r["id"] == identifier
            ]
            if existing:
                return existing[-1]["data"]
            counters = [r for r in self.all() if r["category"] == "counter"]
            last = counters[-1] if counters else {"revision": 0, "data": {"C": 0, "S": 0, "A": 0}}
            numbers = dict(last["data"])

            def take(prefix, count):
                start = numbers[prefix] + 1
                numbers[prefix] += count
                return [f"{prefix}{n:04}" for n in range(start, start + count)]

            keys = {
                "campaign": take("C", 1)[0],
                "adsets": take("S", len(brief.adsets)),
                "ads": take("A", sum(len(s.ads) for s in brief.adsets)),
            }
            self._append("counter", "names", last["revision"], numbers)
            self._append("reservation", identifier, 0, keys)
            return keys

    def save_plan(self, plan):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.get("draft", plan["draft_id"])
            if row["revision"] != plan["draft_revision"]:
                fail("REVISION_CONFLICT", "Brief zmienił się podczas planowania.")
            return self._append("plan", plan["plan_hash"], 0, plan)

    def receipt(self, identifier, data):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            rows = [r for r in self.all() if r["category"] == "execution" and r["id"] == identifier]
            return self._append("execution", identifier, rows[-1]["revision"] if rows else 0, data)

    def execution(self, plan_hash):
        rows = [r for r in self.all() if r["category"] == "execution" and r["id"] == plan_hash]
        return rows[-1]["data"] if rows else {"status": "NOT_STARTED", "operations": {}}

    def describe(self, row):
        return {**row, **readiness(row["data"])}
