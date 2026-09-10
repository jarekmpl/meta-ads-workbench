from datetime import date
from importlib.resources import files
from typing import Protocol

from meta_ads_manager.errors import AppError
from meta_ads_manager.models import Account, ClientProfile, DemoDataset, Goal, Snapshot


class ReadProvider(Protocol):
    def resolve(self, client: str, account: str) -> tuple[ClientProfile, Account]: ...

    def fetch(self, client: str, account: str, since: date, until: date) -> Snapshot: ...


class DemoProvider:
    """Deterministic, packaged data. Never reads credentials or calls the network."""

    def __init__(self, dataset: DemoDataset | None = None):
        self.dataset = dataset or DemoDataset.model_validate_json(
            files("meta_ads_manager").joinpath("fixtures/demo.json").read_text(encoding="utf-8")
        )

    def client(self, client: str) -> ClientProfile:
        profile = next((p for p in self.dataset.profiles if p.client_id == client), None)
        if profile is None:
            raise AppError("SCOPE_MISMATCH", "Nieznany klient w wybranym źródle danych.", 3)
        return profile

    def resolve(self, client: str, account: str) -> tuple[ClientProfile, Account]:
        profile = self.client(client)
        found = next((a for a in profile.accounts if a.account_id == account), None)
        if found is None:
            raise AppError("SCOPE_MISMATCH", "Konto nie należy do wskazanego klienta.", 3)
        return profile, found

    def goal(self, client: str, account: str, goal_id: str) -> Goal:
        profile, _ = self.resolve(client, account)
        goal = next(
            (
                g
                for p in profile.projects
                if account in p.account_ids
                for g in p.goal_profiles
                if g.goal_id == goal_id
            ),
            None,
        )
        if goal is None:
            raise AppError("SCOPE_MISMATCH", "Cel nie należy do wskazanego konta.", 3)
        return goal

    def available(self, client: str, account: str) -> Snapshot:
        self.resolve(client, account)
        snapshot = next(
            (
                s
                for s in self.dataset.snapshots
                if s.client_id == client and s.account_id == account
            ),
            None,
        )
        if snapshot is None:
            raise AppError("INSUFFICIENT_DATA", "Brak danych demonstracyjnych dla konta.", 6)
        return snapshot.model_copy(deep=True)

    def fetch(self, client: str, account: str, since: date, until: date) -> Snapshot:
        snapshot = self.available(client, account)
        if since > until:
            raise AppError("VALIDATION_ERROR", "Początek okresu wypada po jego końcu.", 2)
        if since < snapshot.since or until > snapshot.until:
            raise AppError("INSUFFICIENT_DATA", "Okres wykracza poza dostępne dane demo.", 6)
        payload = snapshot.model_dump(mode="json")
        payload.update(since=since.isoformat(), until=until.isoformat())
        payload["facts"] = [
            fact.model_dump(mode="json") for fact in snapshot.facts if since <= fact.day <= until
        ]
        import json

        return Snapshot.model_validate_json(json.dumps(payload))
