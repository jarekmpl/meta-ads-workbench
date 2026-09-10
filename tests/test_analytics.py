import json
from datetime import date

import pytest

from meta_ads_manager.analytics import aggregate, weekly_review
from meta_ads_manager.errors import AppError
from meta_ads_manager.models import Fact
from meta_ads_manager.provider import DemoProvider


def fact(spend, conversions, impressions=100, clicks=10, value=None):
    return Fact.model_validate_json(
        json.dumps(
            {
                "campaign_id": "demo",
                "day": "2026-09-01",
                "spend": spend,
                "impressions": impressions,
                "link_clicks": clicks,
                "conversions": conversions,
                "conversion_value": value,
            }
        )
    )


def test_ratios_are_recomputed_from_totals_not_averaged():
    result = aggregate([fact("100", "1"), fact("100", "9", 900, 90)], "lead_generation", "PLN")
    assert result["metrics"]["cpl"]["value"] == "20.000000"  # not (100 + 100/9) / 2
    assert result["metrics"]["link_ctr"]["value"] == "10.000000"
    assert result["metrics"]["cpm"]["value"] == "200.000000"
    assert result["metrics"]["reach"]["value"] is None
    assert result["metrics"]["frequency"]["reason"] == "non_additive_unavailable"


def test_zero_and_missing_conversions_are_different():
    zero = aggregate([fact("100", "0")], "lead_generation", "PLN")
    missing = aggregate([fact("100", None), fact("100", "5")], "lead_generation", "PLN")
    assert zero["totals"]["conversions"] == "0"
    assert zero["metrics"]["cpl"]["reason"] == "zero_denominator"
    assert missing["totals"]["conversions"] is None
    assert missing["metrics"]["cpl"]["reason"] == "unavailable"


def test_revenue_unavailable_is_not_zero_roas():
    result = aggregate([fact("50", "1", value=None)], "ecommerce", "PLN")
    assert result["metrics"]["roas"]["reason"] == "unavailable"
    result = aggregate([fact("0", "0", value="0")], "ecommerce", "PLN")
    assert result["metrics"]["roas"]["reason"] == "zero_denominator"


def test_weekly_report_known_values_and_evidence():
    provider = DemoProvider()
    snapshot = provider.available("demo-shop", "act_DEMO_SHOP")
    goal = provider.goal("demo-shop", "act_DEMO_SHOP", "commerce-pl")
    result = weekly_review("sync_example", snapshot, goal)
    assert result["summary"]["current"]["totals"]["spend"] == "1400.00"
    assert result["summary"]["current"]["totals"]["conversions"] == "35"
    assert result["summary"]["current"]["metrics"]["cpa"]["value"] == "40.000000"
    assert result["summary"]["current"]["metrics"]["roas"]["value"] == "4.500000"
    assert result["evidence_refs"] == ["sync_example"]
    assert result["target_checks"]["roas"]["status"] == "met"
    assert result["recommendations"] == []


def test_weekly_report_requires_full_previous_period():
    provider = DemoProvider()
    snapshot = provider.fetch("demo-leads", "act_DEMO_LEADS", date(2026, 9, 2), date(2026, 9, 8))
    goal = provider.goal("demo-leads", "act_DEMO_LEADS", "leads-pl")
    with pytest.raises(AppError, match="14 pełnych dni"):
        weekly_review("sync_example", snapshot, goal)
