import copy
import io
import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import SecretStr

from meta_ads_manager.cli import run
from meta_ads_manager.errors import AppError
from meta_ads_manager.meta_connection import (
    Connection,
    Credentials,
    MetaReadClient,
    config_path,
    save_private,
    secret_path,
)
from meta_ads_manager.meta_provider import MetaProvider, profile_from_snapshot
from meta_ads_manager.reporting import account_audit, account_report

SINCE = date(2026, 8, 10)
UNTIL = date(2026, 9, 8)
ACCOUNT = {
    "id": "act_456",
    "account_id": "456",
    "name": "Test",
    "currency": "USD",
    "timezone_name": "Europe/Warsaw",
}
CAMPAIGNS = [
    {
        "id": "101",
        "account_id": "456",
        "name": "Active",
        "status": "ACTIVE",
        "objective": "OUTCOME_LEADS",
    },
    {
        "id": "102",
        "account_id": "456",
        "name": "Paused",
        "status": "PAUSED",
        "objective": "LINK_CLICKS",
    },
    {"id": "103", "account_id": "456", "name": "Deleted", "status": "DELETED"},
]
ROW = {
    "account_id": "456",
    "account_currency": "USD",
    "campaign_id": "101",
    "campaign_name": "Active",
    "objective": "OUTCOME_LEADS",
    "date_start": "2026-09-01",
    "date_stop": "2026-09-01",
    "spend": "12.30",
    "impressions": "100",
    "inline_link_clicks": "3",
    "actions": [
        {"action_type": "lead", "value": "0.5"},
        {"action_type": "onsite_conversion.lead_grouped", "value": "0.5"},
    ],
}
TOTAL = {
    "account_id": "456",
    "account_currency": "USD",
    "date_start": str(SINCE),
    "date_stop": str(UNTIL),
    "spend": "12.30",
    "impressions": "100",
    "inline_link_clicks": "3",
}


@pytest.fixture
def configured(tmp_path):
    connection = Connection(
        client_id="firma", app_id="123", account_id="act_456", api_version="v26.0"
    )
    save_private(config_path(tmp_path, "firma"), connection.model_dump(mode="json"))
    save_private(secret_path(tmp_path, "firma"), {"app_id": "123", "access_token": "FAKE_SECRET"})
    return tmp_path


def fake_api(monkeypatch, inventory=None, rows=None, totals=None):
    get = MagicMock(return_value=ACCOUNT)
    pages = MagicMock(
        side_effect=[
            copy.deepcopy(CAMPAIGNS if inventory is None else inventory),
            copy.deepcopy([ROW] if rows is None else rows),
            copy.deepcopy([TOTAL] if totals is None else totals),
        ]
    )
    monkeypatch.setattr(MetaReadClient, "get", get)
    monkeypatch.setattr(MetaReadClient, "pages", pages)
    return get, pages


def test_live_snapshot_includes_inactive_campaigns_and_preserves_action_aliases(
    configured, monkeypatch
):
    _, pages = fake_api(monkeypatch)
    snapshot = MetaProvider(configured, "firma", "act_456").fetch(SINCE, UNTIL)
    assert snapshot.source == "meta" and len(snapshot.campaigns) == 3
    assert len(snapshot.facts) == 90
    assert snapshot.meta.reconciliation == "matched"
    report = account_report("sync_test", snapshot, profile_from_snapshot(snapshot), SINCE, UNTIL)
    assert report["summary"]["totals"] == {"spend": "12.30", "impressions": 100, "link_clicks": 3}
    active = report["campaigns"][0]
    assert active["reported_actions"] == {"lead": "0.5", "onsite_conversion.lead_grouped": "0.5"}
    assert "conversions" not in active["totals"] and active["measurement_status"] == "unmapped"
    assert report["campaigns"][1]["totals"]["spend"] == "0"
    assert not any("syntetyczne" in text for text in report["limitations"])
    assert "ARCHIVED" in pages.call_args_list[0].args[1]["effective_status"]
    assert "DELETED" not in pages.call_args_list[0].args[1]["effective_status"]


@pytest.mark.parametrize("inventory", [[], CAMPAIGNS])
def test_empty_period_is_zero_delivery_not_missing_measurement(configured, monkeypatch, inventory):
    fake_api(monkeypatch, inventory=inventory, rows=[], totals=[])
    snapshot = MetaProvider(configured, "firma", "act_456").fetch(SINCE, UNTIL)
    report = account_report("sync_test", snapshot, profile_from_snapshot(snapshot), SINCE, UNTIL)
    assert report["summary"]["totals"]["spend"] == "0"
    assert report["summary"]["metrics"]["cpm"]["value"] is None
    assert report["campaign_count"] == len(inventory)
    assert all(f.conversions is None for f in snapshot.facts)
    assert [r["code"] for r in account_audit(report)["recommendations"]] == ["NO_SPEND"]


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("foreign", "SCOPE_MISMATCH"),
        ("currency", "SCOPE_MISMATCH"),
        ("duplicate", "INCOMPLETE_DATA"),
        ("missing", "RECONCILIATION_FAILED"),
        ("outside", "SCOPE_MISMATCH"),
        ("malformed", "API_RESPONSE"),
    ],
)
def test_invalid_or_incomplete_insights_never_become_zeroes(
    configured, monkeypatch, mutation, code
):
    rows = [copy.deepcopy(ROW)]
    if mutation == "foreign":
        rows[0]["account_id"] = "999"
    elif mutation == "currency":
        rows[0]["account_currency"] = "PLN"
    elif mutation == "duplicate":
        rows.append(copy.deepcopy(ROW))
    elif mutation == "missing":
        rows = []
    elif mutation == "outside":
        rows[0]["date_start"] = rows[0]["date_stop"] = "2026-07-01"
    else:
        rows[0]["spend"] = "NaN"
    fake_api(monkeypatch, rows=rows)
    with pytest.raises(AppError) as error:
        MetaProvider(configured, "firma", "act_456").fetch(SINCE, UNTIL)
    assert error.value.code == code


def test_insights_only_campaign_is_retained(configured, monkeypatch):
    fake_api(monkeypatch, inventory=[])
    snapshot = MetaProvider(configured, "firma", "act_456").fetch(SINCE, UNTIL)
    assert snapshot.campaigns[0].status == "UNKNOWN"
    assert snapshot.campaigns[0].campaign_id == "101"


def test_scope_rejected_before_loading_credentials(configured, monkeypatch):
    load = MagicMock(side_effect=AssertionError("must not read token"))
    monkeypatch.setattr("meta_ads_manager.meta_provider.load_credentials", load)
    with pytest.raises(AppError) as error:
        MetaProvider(configured, "firma", "act_999")
    assert error.value.code == "SCOPE_MISMATCH"
    load.assert_not_called()


def paging_client(payloads):
    api = MetaReadClient(
        Connection(client_id="firma", app_id="123", account_id="act_456", api_version="v26.0"),
        Credentials(app_id="123", access_token=SecretStr("FAKE_SECRET")),
    )
    api.opener = MagicMock()
    responses = []
    for payload in payloads:
        response = MagicMock()
        response.__enter__.return_value = io.BytesIO(json.dumps(payload).encode())
        responses.append(response)
    api.opener.open.side_effect = responses
    return api


def test_pagination_uses_cursor_and_fixed_host_never_next_url():
    api = paging_client(
        [
            {
                "data": [{"id": "1"}],
                "paging": {
                    "next": "https://evil.example/?access_token=LEAK",
                    "cursors": {"after": "cursor1"},
                },
            },
            {"data": [{"id": "2"}]},
        ]
    )
    assert api.pages("campaigns", {"limit": "1"}) == [{"id": "1"}, {"id": "2"}]
    urls = [call.args[0].full_url for call in api.opener.open.call_args_list]
    assert all(urlparse(url).netloc == "graph.facebook.com" for url in urls)
    assert parse_qs(urlparse(urls[1]).query)["after"] == ["cursor1"]
    assert "LEAK" not in str(urls) and "FAKE_SECRET" not in str(urls)


@pytest.mark.parametrize(
    "paging", [{"next": "ignored"}, {"next": "ignored", "cursors": {"after": "same"}}]
)
def test_broken_or_repeated_cursor_fails(paging):
    api = paging_client([{"data": [], "paging": paging}] * 2)
    with pytest.raises(AppError) as error:
        api.pages("campaigns", {})
    assert error.value.code == "INCOMPLETE_DATA"


def test_end_to_end_live_cli_reports_are_offline_and_isolated(configured, monkeypatch, capsys):
    monkeypatch.chdir(configured)
    get, pages = fake_api(monkeypatch)
    scope = ["--client", "firma", "--account", "act_456"]
    period = ["--since", str(SINCE), "--until", str(UNTIL)]
    assert run(["sync", *scope, *period]) == 0
    sync = json.loads(capsys.readouterr().out)
    assert Path("data/meta.sqlite3").exists() and not Path("data/demo.sqlite3").exists()
    get.side_effect = AssertionError("offline report must not access network")
    pages.side_effect = AssertionError("offline report must not access network")
    assert run(["report", "campaigns", *scope, *period, "--snapshot", sync["data"]["run_id"]]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["data"]["source"] == "meta" and report["data"]["campaign_count"] == 3
    assert report["warnings"] == []
    assert run(["report", "show", *scope, "--run", report["data"]["run_id"]]) == 0
    saved = json.loads(capsys.readouterr().out)
    assert saved["data"] == report["data"]
    assert run(["audit", *scope, *period]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["status"] == "PARTIAL"
    assert run(["report", "campaigns", "--client", "firma", "--account", "act_999", *period]) == 3
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "SCOPE_MISMATCH"


def test_failed_sync_does_not_create_success_snapshot(configured, monkeypatch, capsys):
    monkeypatch.chdir(configured)
    fake_api(monkeypatch, rows=[])
    assert (
        run(
            [
                "sync",
                "--client",
                "firma",
                "--account",
                "act_456",
                "--since",
                str(SINCE),
                "--until",
                str(UNTIL),
            ]
        )
        == 5
    )
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "RECONCILIATION_FAILED"
    assert not Path("data/meta.sqlite3").exists()
