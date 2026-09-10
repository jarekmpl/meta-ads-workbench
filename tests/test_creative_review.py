import io
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from meta_ads_manager.creative_media import check_media_url
from meta_ads_manager.creative_review import (
    CreativeAPI,
    Evidence,
    action,
    choose_sample,
    metrics,
    validate_rows,
)
from meta_ads_manager.errors import AppError
from meta_ads_manager.meta_connection import Connection, Credentials


def api():
    return CreativeAPI(
        Connection(client_id="test", account_id="act_1", app_id="1", api_version="v26.0"),
        Credentials(app_id="1", access_token=SecretStr("DO_NOT_PRINT")),
    )


def test_explicit_windows_do_not_fall_back_or_double_count_aliases():
    row = {"spend": "100", "impressions": "1000", "actions": [
        {"action_type": "onsite_conversion.lead_grouped", "value": "9", "7d_click": "2"},
        {"action_type": "lead", "value": "20"},
    ]}
    assert action(row, "onsite_conversion.lead_grouped") == Decimal(2)
    assert action(row, "lead") is None
    assert metrics(row)["native_cpl_7d_click"] == "50"
    assert metrics(row)["web_cpl_7d_click"] is None


def test_pagination_uses_cursor_not_token_url_and_does_not_return_partial():
    client = api()
    client.get = MagicMock(side_effect=[
        {"data": [{"id": "a"}], "paging": {"next": "https://evil/?token=secret",
                                             "cursors": {"after": "same"}}},
        {"data": [{"id": "b"}], "paging": {"next": "yes", "cursors": {"after": "same"}}},
    ])
    with pytest.raises(AppError, match="paginacja"):
        client.pages("act_1/insights", {})
    assert client.get.call_args.args[0] == "act_1/insights"
    assert client.get.call_args.args[1] == {"after": "same"}


def test_request_scope_and_authentication():
    client = api()
    with pytest.raises(AppError):
        client.get("999", {})
    with pytest.raises(AppError):
        client.get("act_1/ads/delete", {})
    client.opener = MagicMock()
    client.opener.open.return_value.__enter__.return_value = io.BytesIO(b'{"data":[]}')
    client.get("act_1/insights", {})
    req = client.opener.open.call_args.args[0]
    assert req.method == "GET" and "DO_NOT_PRINT" not in req.full_url
    assert req.get_header("Authorization") == "Bearer DO_NOT_PRINT"


def test_cdn_allowlist_cannot_be_bypassed():
    check_media_url("https://scontent.xx.fbcdn.net/file.jpg?signed=yes")
    for url in ["http://scontent.xx.fbcdn.net/a", "https://fbcdn.net.evil.test/a",
                "https://localhost/a", "https://user@fbcdn.net/a",
                "https://fbcdn.net/a?access_token=secret"]:
        with pytest.raises(AppError):
            check_media_url(url)


def test_resume_rejects_different_scope_and_request(tmp_path):
    e = Evidence(tmp_path, {"account": "1"})
    client = MagicMock()
    client.pages.return_value = [{"id": "a"}]
    assert e.fetch("rows", client, "act_1/insights", {}) == [{"id": "a"}]
    with pytest.raises(AppError):
        Evidence(tmp_path, {"account": "2"})
    with pytest.raises(AppError):
        e.fetch("rows", client, "act_1/insights", {"new": "request"})
    client.pages.side_effect = AppError("API_PARAMETER", "Unavailable", 5)
    assert e.fetch("optional", client, "act_1/insights", {}, optional=True) is None
    assert not (tmp_path / "optional.json").exists()
    assert e.errors[0]["code"] == "API_PARAMETER"


def test_wrong_scope_dates_duplicates_fail():
    row = {"account_id": "1", "account_currency": "PLN", "ad_id": "10",
           "date_start": "2026-08-10", "date_stop": "2026-09-08"}
    validate_rows([row], "act_1", "PLN", "2026-08-10", "2026-09-08")
    for rows in [[{**row, "account_id": "2"}], [row, row],
                 [{**row, "date_stop": "2026-09-09"}]]:
        with pytest.raises(AppError):
            validate_rows(rows, "act_1", "PLN", "2026-08-10", "2026-09-08")


def test_sample_is_deterministic_unique_and_includes_lower_exposure():
    rows = [{"ad_id": str(i), "campaign_id": str(i // 5), "spend": str(i + 1),
             "impressions": "100"} for i in range(30)]
    ids, reasons = choose_sample(rows, 12)
    assert len(ids) == len(set(ids)) == 12
    assert choose_sample(list(reversed(rows)), 12)[0] == ids
    assert "low_exposure_comparison" in reasons.values()
    assert choose_sample([], 12) == ([], {})
