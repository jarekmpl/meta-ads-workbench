from datetime import date

import pytest

from meta_ads_manager.errors import AppError
from meta_ads_manager.provider import DemoProvider
from meta_ads_manager.reporting import account_audit, account_report


def make_report():
    provider = DemoProvider()
    return account_report(
        "sync_test",
        provider.available("demo-shop", "act_DEMO_SHOP"),
        provider.client("demo-shop"),
        date(2026, 8, 10),
        date(2026, 9, 8),
    )


def test_thirty_day_report_includes_all_campaigns_and_correct_totals():
    report = make_report()
    assert report["campaign_count"] == 2
    assert all(row["status_at_snapshot"] == "PAUSED" for row in report["campaigns"])
    assert report["summary"]["totals"]["spend"] == "5080.00"
    assert report["goal_groups"][0]["totals"]["conversions"] == "127"
    assert report["goal_groups"][0]["metrics"]["roas"]["value"] == "4.500000"
    assert "conversions" not in report["summary"]["totals"]
    assert "roas" not in report["summary"]["metrics"]


def test_no_silent_truncation_of_requested_period():
    provider = DemoProvider()
    snapshot = provider.fetch("demo-shop", "act_DEMO_SHOP", date(2026, 8, 26), date(2026, 9, 8))
    with pytest.raises(AppError, match="całego"):
        account_report(
            "sync_test", snapshot, provider.client("demo-shop"), date(2026, 8, 10), date(2026, 9, 8)
        )


def test_audit_marks_unavailable_areas_and_recommendations_with_evidence():
    report = account_audit(make_report())
    assert report["status"] == "PARTIAL"
    coverage = {entry["area"]: entry["status"] for entry in report["coverage"]}
    assert coverage["creative"] == "unavailable"
    assert coverage["targeting"] == "unavailable"
    assert coverage["reported_performance"] == "checked"
    assert report["recommendations"]
    assert all(item["evidence_refs"] == ["sync_test"] for item in report["recommendations"])
    assert all(item["execution"] == "recommendation_only" for item in report["recommendations"])


def test_unmapped_campaign_is_not_dropped_or_given_a_cost_per_outcome():
    provider = DemoProvider()
    snapshot = provider.available("demo-shop", "act_DEMO_SHOP")
    snapshot.campaigns[0].goal_id = "unknown"
    report = account_report(
        "sync_test", snapshot, provider.client("demo-shop"), date(2026, 8, 10), date(2026, 9, 8)
    )
    assert report["campaign_count"] == 2
    assert report["campaigns"][0]["measurement_status"] == "unmapped"
    assert "cpa" not in report["campaigns"][0]["metrics"]
    assert any(item["code"] == "UNMAPPED_GOAL" for item in account_audit(report)["recommendations"])


def test_profile_of_another_client_is_rejected():
    provider = DemoProvider()
    with pytest.raises(AppError, match="Profil"):
        account_report(
            "sync_test",
            provider.available("demo-shop", "act_DEMO_SHOP"),
            provider.client("demo-leads"),
            date(2026, 8, 10),
            date(2026, 9, 8),
        )


def test_missing_conversions_yield_data_check_not_a_budget_change():
    report = make_report()
    report["campaigns"][0]["totals"]["conversions"] = None
    report["campaigns"][0]["metrics"]["cpa"]["value"] = None
    findings = account_audit(report)["recommendations"]
    item = next(item for item in findings if item["code"] == "CHECK_CONVERSION_DATA")
    assert item["evidence"]["conversions"] is None
    assert item["execution"] == "recommendation_only"


def test_different_business_goals_remain_separate():
    provider = DemoProvider()
    snapshot = provider.available("demo-shop", "act_DEMO_SHOP")
    profile = provider.client("demo-shop").model_copy(deep=True)
    profile.projects[0].goal_profiles.append(
        provider.goal("demo-leads", "act_DEMO_LEADS", "leads-pl")
    )
    snapshot.campaigns[0].goal_id = "leads-pl"
    report = account_report("sync_test", snapshot, profile, date(2026, 8, 10), date(2026, 9, 8))
    assert len(report["goal_groups"]) == 2
    assert {row["goal_type"] for row in report["campaigns"]} == {"lead_generation", "ecommerce"}
    assert "conversions" not in report["summary"]["totals"]
