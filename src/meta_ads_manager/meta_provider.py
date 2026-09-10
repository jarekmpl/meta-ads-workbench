"""Read-only Meta ingestion with complete pagination and account reconciliation."""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from meta_ads_manager.errors import AppError
from meta_ads_manager.meta_connection import MetaReadClient, load_connection, load_credentials
from meta_ads_manager.models import Account, ClientProfile, Snapshot

STATUSES = ["ACTIVE", "PAUSED", "ARCHIVED", "DELETED", "IN_PROCESS", "WITH_ISSUES"]


def invalid_response():
    return AppError("API_RESPONSE", "Dane Meta są niepełne lub mają niepoprawny format.", 5)


def decimal_value(value) -> Decimal:
    if not isinstance(value, str):
        raise invalid_response()
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise invalid_response() from None
    if not number.is_finite() or number < 0:
        raise invalid_response()
    return number


def integer_value(value) -> int:
    number = decimal_value(value)
    if number != number.to_integral_value():
        raise invalid_response()
    return int(number)


def counts(row: dict) -> tuple[Decimal, int, int]:
    return (
        decimal_value(row.get("spend")),
        integer_value(row.get("impressions")),
        integer_value(row.get("inline_link_clicks", "0")),
    )


def action_map(row: dict, key: str) -> dict[str, str]:
    # Keep overlapping Meta action types separate; never sum aliases into conversions.
    values = row.get(key, [])
    if not isinstance(values, list):
        raise invalid_response()
    result = {}
    for value in values:
        if not isinstance(value, dict):
            raise invalid_response()
        action = value.get("action_type")
        if not isinstance(action, str) or not action or action in result:
            raise invalid_response()
        result[action] = str(decimal_value(value.get("value")))
    return result


def profile_for(client: str, account: Account, name: str) -> ClientProfile:
    return ClientProfile(
        schema_version="1.0",
        kind="client_profile",
        client_id=client,
        name=name,
        accounts=[account],
        projects=[],
        policy={
            "version": "1",
            "mode": "analyst",
            "allowed_write_operations": [],
            "automation_enabled": False,
        },
    )


def profile_from_snapshot(snapshot: Snapshot) -> ClientProfile:
    return profile_for(
        snapshot.client_id,
        Account(
            account_id=snapshot.account_id,
            credential_ref=f"local:{snapshot.client_id}",
            currency=snapshot.spec.currency,
            timezone=snapshot.spec.timezone,
        ),
        snapshot.meta.account_name,
    )


def configured_clients(root: Path) -> list[dict]:
    result = []
    for path in sorted((root / "config" / "local").glob("meta-*.json")):
        client = path.stem.removeprefix("meta-")
        connection = load_connection(root, client)
        result.append({"client_id": client, "account_id": connection.account_id})
    return result


def validate_scope(root: Path, client: str, account: str):
    connection = load_connection(root, client)
    if connection.account_id != account:
        raise AppError("SCOPE_MISMATCH", "Konto nie jest przypisane do wskazanego klienta.", 3)
    return connection


def report_period(args, timezone: str, default_days: int = 30) -> tuple[date, date]:
    if (args.since is None) != (args.until is None):
        raise AppError("VALIDATION_ERROR", "Podaj razem --since i --until.", 2)
    if args.last_days is not None and args.since is not None:
        raise AppError("VALIDATION_ERROR", "Nie łącz --last-days z konkretnymi datami.", 2)
    yesterday = datetime.now(ZoneInfo(timezone)).date() - timedelta(days=1)
    until = args.until or yesterday
    since = args.since or until - timedelta(days=(args.last_days or default_days) - 1)
    if since > until or until > yesterday:
        raise AppError("VALIDATION_ERROR", "Podaj poprawny okres obejmujący pełne dni.", 2)
    if (until - since).days >= 366:
        raise AppError("VALIDATION_ERROR", "Jeden odczyt Meta obsługuje najwyżej 366 dni.", 2)
    return since, until


class MetaProvider:
    def __init__(self, root: Path, client: str, account: str):
        self.connection = validate_scope(root, client, account)
        self.api = MetaReadClient(self.connection, load_credentials(root, self.connection))
        self.profile = None

    def resolve(self) -> ClientProfile:
        if self.profile is None:
            raw = self.api.get("account")
            if raw.get("id") != self.connection.account_id:
                raise AppError("SCOPE_MISMATCH", "Meta zwróciła inne konto.", 3)
            if raw.get("account_id") != self.connection.account_id.removeprefix("act_"):
                raise AppError("SCOPE_MISMATCH", "Niezgodny numer konta w odpowiedzi Meta.", 3)
            account = Account(
                account_id=raw["id"],
                credential_ref=f"local:{self.connection.client_id}",
                currency=raw.get("currency"),
                timezone=raw.get("timezone_name"),
            )
            self.profile = profile_for(self.connection.client_id, account, raw.get("name"))
        return self.profile

    def fetch(self, since: date, until: date) -> Snapshot:
        profile = self.resolve()
        account = profile.accounts[0]
        today = datetime.now(ZoneInfo(account.timezone)).date()
        if since > until or until >= today or (until - since).days >= 366:
            raise AppError("VALIDATION_ERROR", "Niepoprawny okres synchronizacji Meta.", 2)
        inventory = self.api.pages(
            "campaigns",
            {
                "fields": "id,account_id,name,status,objective",
                "effective_status": json.dumps([s for s in STATUSES if s != "DELETED"]),
                "limit": "100",
            },
        )
        common = {
            "time_range": json.dumps({"since": str(since), "until": str(until)}),
            "action_attribution_windows": json.dumps(["7d_click", "1d_view"]),
            "action_report_time": "impression",
            "limit": "500",
            "filtering": json.dumps(
                [{"field": "campaign.effective_status", "operator": "IN", "value": STATUSES}]
            ),
        }
        rows = self.api.pages(
            "insights",
            {
                **common,
                "level": "campaign",
                "time_increment": "1",
                "fields": "account_id,account_currency,campaign_id,campaign_name,objective,"
                "date_start,date_stop,spend,impressions,inline_link_clicks,actions,action_values",
            },
        )
        totals = self.api.pages(
            "insights",
            {
                **common,
                "level": "account",
                "fields": "account_id,account_currency,date_start,date_stop,spend,impressions,"
                "inline_link_clicks",
            },
        )
        campaigns = {}
        number = account.account_id.removeprefix("act_")
        for item in inventory:
            campaign_id = item.get("id")
            if item.get("account_id") != number:
                raise AppError("SCOPE_MISMATCH", "Kampania pochodzi z innego konta.", 3)
            if not isinstance(campaign_id, str) or not campaign_id.isdigit():
                raise invalid_response()
            if campaign_id in campaigns:
                raise AppError("INCOMPLETE_DATA", "Powtórzona kampania; ponów synchronizację.", 5)
            campaigns[campaign_id] = {
                "campaign_id": campaign_id,
                "name": item.get("name"),
                "goal_id": None,
                "status": item.get("status"),
                "objective": item.get("objective"),
            }
        facts = {}
        row_totals = [Decimal(0), 0, 0]
        for row in rows:
            self.validate_row_scope(row, number, account.currency)
            try:
                day = date.fromisoformat(row["date_start"])
            except (KeyError, TypeError, ValueError):
                raise invalid_response() from None
            if str(day) != row.get("date_stop") or not since <= day <= until:
                raise AppError("SCOPE_MISMATCH", "Wyniki Meta wykraczają poza okres.", 3)
            campaign_id = row.get("campaign_id")
            if not isinstance(campaign_id, str) or not campaign_id.isdigit():
                raise invalid_response()
            key = (campaign_id, day)
            if key in facts:
                raise AppError(
                    "INCOMPLETE_DATA", "Powtórzone wyniki dnia; ponów synchronizację.", 5
                )
            # Insights may still expose an object no longer returned by inventory.
            if campaign_id not in campaigns:
                campaigns[campaign_id] = {
                    "campaign_id": campaign_id,
                    "name": row.get("campaign_name"),
                    "goal_id": None,
                    "status": "UNKNOWN",
                    "objective": row.get("objective"),
                }
            spend, impressions, clicks = counts(row)
            row_totals = [
                a + b for a, b in zip(row_totals, (spend, impressions, clicks), strict=True)
            ]
            facts[key] = {
                "campaign_id": campaign_id,
                "day": str(day),
                "spend": str(spend),
                "impressions": impressions,
                "link_clicks": clicks,
                "conversions": None,
                "conversion_value": None,
                "actions": action_map(row, "actions"),
                "action_values": action_map(row, "action_values"),
            }
        if len(totals) > 1:
            raise invalid_response()
        if totals:
            self.validate_row_scope(totals[0], number, account.currency)
            if totals[0].get("date_start") != str(since) or totals[0].get("date_stop") != str(
                until
            ):
                raise AppError("SCOPE_MISMATCH", "Podsumowanie dotyczy innego okresu.", 3)
            expected = counts(totals[0])
        else:
            expected = (Decimal(0), 0, 0)
        if tuple(row_totals) != expected:
            raise AppError(
                "RECONCILIATION_FAILED",
                "Suma kampanii różni się od podsumowania konta. "
                "Snapshot nie został zapisany; ponów odczyt lub zawęź okres.",
                5,
                retryable=True,
            )
        # Fill absent delivery only after all pages and account totals were verified.
        for campaign_id in campaigns:
            for offset in range((until - since).days + 1):
                day = since + timedelta(days=offset)
                facts.setdefault(
                    (campaign_id, day),
                    {
                        "campaign_id": campaign_id,
                        "day": str(day),
                        "spend": "0",
                        "impressions": 0,
                        "link_clicks": 0,
                        "conversions": None,
                        "conversion_value": None,
                        "inferred_no_delivery": True,
                    },
                )
        return Snapshot.model_validate_json(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "kind": "snapshot",
                    "client_id": profile.client_id,
                    "account_id": account.account_id,
                    "source": "meta",
                    "since": str(since),
                    "until": str(until),
                    "fetched_at": datetime.now(UTC).isoformat(),
                    "complete": True,
                    "spec": {
                        "level": "campaign",
                        "currency": account.currency,
                        "timezone": account.timezone,
                        "click_type": "link_click",
                        "attribution": "7d_click_1d_view",
                        "action_report_time": "impression",
                        "api_version": self.connection.api_version,
                        "normalization_version": "1",
                    },
                    "campaigns": sorted(campaigns.values(), key=lambda c: c["campaign_id"]),
                    "facts": [facts[key] for key in sorted(facts)],
                    "meta": {
                        "account_name": profile.name,
                        "inventory_count": len(inventory),
                        "insight_row_count": len(rows),
                        "account_spend": str(expected[0]),
                        "account_impressions": expected[1],
                        "account_link_clicks": expected[2],
                        "reconciliation": "matched",
                    },
                }
            )
        )

    @staticmethod
    def validate_row_scope(row: dict, account_number: str, currency: str):
        if row.get("account_id") != account_number or row.get("account_currency") != currency:
            raise AppError("SCOPE_MISMATCH", "Wyniki mają inne konto lub walutę.", 3)
