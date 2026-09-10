import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from meta_ads_manager.cli import run
from meta_ads_manager.decision_models import (
    BusinessGoal,
    CampaignGoalAssignment,
    Recommendation,
    RecommendationEvent,
)
from meta_ads_manager.decision_store import Decisions
from meta_ads_manager.errors import AppError
from meta_ads_manager.goal_reporting import calculate, evaluate, measurements
from meta_ads_manager.models import Snapshot
from meta_ads_manager.storage import Store

SCOPE = {"schema_version": "1.0", "client_id": "client-a", "account_id": "act_123"}
START = date(2026, 8, 26)


def parse(model, raw):
    return model.model_validate_json(json.dumps(raw))


def goal(**updates):
    return parse(
        BusinessGoal,
        {
            **SCOPE,
            "kind": "business_goal",
            "goal_id": "leads-form",
            "expected_revision": 0,
            "project_id": "main",
            "name": "Leady formularzowe",
            "business_outcome": "Pozyskanie leada",
            "result_label": "Lead z formularza",
            "result_type": "lead",
            "measurement_role": "primary",
            "conversion_location": "meta_instant_form",
            "action_type": "onsite_conversion.lead_grouped",
            "currency": "PLN",
            "targets": {"cost_per_result": "50"},
            "confirmed_by": "Operator",
            "confirmation_ref": "Przykładowe ustalenie",
            **updates,
        },
    )


def assignment(**updates):
    return parse(
        CampaignGoalAssignment,
        {
            **SCOPE,
            "kind": "campaign_goal_assignment",
            "campaign_id": "101",
            "goal_id": "leads-form",
            "goal_revision": 1,
            "expected_revision": 0,
            "effective_from": str(START),
            "confirmed_by": "Operator",
            "confirmation_ref": "Przykładowa decyzja",
            **updates,
        },
    )


def recommendation(**updates):
    raw = {
        **SCOPE,
        "kind": "recommendation",
        "recommendation_id": "rec-1",
        "goal_id": "leads-form",
        "goal_revision": 1,
        "campaign_ids": ["101"],
        "title": "Test komunikatu",
        "action": "Sprawdź inny argument oferty.",
        "rationale": "Wnioski z przykładowej analizy.",
        "priority": "medium",
        "evidence_refs": ["synthetic-baseline"],
        "test_plan": {
            "hypothesis": "Inny argument obniży koszt leada.",
            "method": "before_after",
            "baseline": {"since": str(START), "until": "2026-09-01"},
            "evaluation_days": 7,
            "metric": "cost_per_result",
            "direction": "decrease",
            "success_threshold": "40",
            "minimum_results": "10",
            "stop_condition": "Operator przerwie test po wyczerpaniu jego budżetu.",
        },
    }
    raw.update(updates)
    return parse(Recommendation, raw)


def event(action, revision, **updates):
    return parse(
        RecommendationEvent,
        {
            **SCOPE,
            "kind": "recommendation_event",
            "event_id": f"event-{action}",
            "recommendation_id": "rec-1",
            "expected_revision": revision,
            "event": action,
            "actor": "Operator",
            "reason": "Decyzja testowa",
            "evidence_refs": ["synthetic-operator-message"],
            **updates,
        },
    )


@pytest.fixture
def snapshot():
    facts = []
    for n in range(14):
        facts.append(
            {
                "campaign_id": "101",
                "day": str(START + timedelta(days=n)),
                "spend": "100",
                "impressions": 1000,
                "link_clicks": 10,
                "conversions": None,
                "conversion_value": None,
                "actions": {"onsite_conversion.lead_grouped": "2" if n < 7 else "4", "lead": "999"},
            }
        )
    return parse(
        Snapshot,
        {
            **SCOPE,
            "kind": "snapshot",
            "source": "meta",
            "since": str(START),
            "until": "2026-09-08",
            "fetched_at": "2026-09-10T09:00:00+00:00",
            "complete": True,
            "spec": {
                "level": "campaign",
                "currency": "PLN",
                "timezone": "Europe/Warsaw",
                "click_type": "link_click",
                "attribution": "7d_click_1d_view",
                "action_report_time": "impression",
                "api_version": "v26.0",
                "normalization_version": "1",
            },
            "campaigns": [
                {
                    "campaign_id": "101",
                    "goal_id": None,
                    "name": "Test campaign",
                    "status": "PAUSED",
                    "objective": "OUTCOME_LEADS",
                }
            ],
            "facts": facts,
            "meta": {
                "account_name": "Synthetic",
                "inventory_count": 1,
                "insight_row_count": 14,
                "account_spend": "1400",
                "account_impressions": 14000,
                "account_link_clicks": 140,
                "reconciliation": "matched",
            },
        },
    )


@pytest.fixture
def registry(tmp_path):
    with Decisions(tmp_path / "decisions.sqlite3", "client-a", "act_123") as store:
        store.save_goal(goal())
        store.assign(assignment())
        yield store


def test_goal_versions_are_immutable_and_conflicts_do_not_write(registry):
    updated = goal(expected_revision=1, targets={"cost_per_result": "30"})
    assert registry.save_goal(updated)["revision"] == 2
    assert registry.save_goal(updated)["revision"] == 2
    assert registry.get("goal", "leads-form", 1)["data"]["targets"]["cost_per_result"] == "50"
    with pytest.raises(AppError, match="zmienił"):
        registry.save_goal(goal(expected_revision=1, targets={"cost_per_result": "20"}))
    assert registry.get("goal", "leads-form")["revision"] == 2


def test_accounts_and_clients_are_scoped(tmp_path, registry):
    with pytest.raises(AppError):
        registry.save_goal(goal(client_id="client-b"))
    with Decisions(tmp_path / "decisions.sqlite3", "client-b", "act_999") as other:
        with pytest.raises(AppError):
            other.get("goal", "leads-form")
    with pytest.raises(AppError, match="właściciela"):
        Decisions(tmp_path / "decisions.sqlite3", "client-b", "act_123")


def test_exact_action_not_sum_of_overlapping_aliases(snapshot, registry):
    before = snapshot.model_dump_json()
    result = measurements(snapshot, snapshot.since, snapshot.until, registry.all())
    row = result["groups"][0]
    assert row["totals"]["results"] == "42"
    assert row["metrics"]["cost_per_result"]["value"] == "33.333333"
    assert row["target_checks"]["cost_per_result"]["status"] == "met"
    assert snapshot.model_dump_json() == before


def test_missing_is_not_zero_without_explicit_rule(snapshot):
    snapshot.facts[0].actions = {}
    result = calculate(snapshot.facts, goal(), snapshot.spec)
    assert result["totals"]["results"] is None
    assert result["totals"]["reported_results"] == "40"
    assert result["metrics"]["cost_per_result"]["value"] is None
    assert result["coverage"]["days_without_action"] == 1
    result = calculate(
        snapshot.facts, goal(missing_action_policy="zero_when_omitted"), snapshot.spec
    )
    assert result["totals"]["results"] == "40"


def test_zero_is_distinct_from_missing(snapshot):
    for fact in snapshot.facts:
        fact.actions["onsite_conversion.lead_grouped"] = 0
    result = calculate(snapshot.facts, goal(), snapshot.spec)
    assert result["totals"]["results"] == "0"
    assert result["metrics"]["cost_per_result"]["reason"] == "zero_denominator"


def test_currency_mismatch_blocks_metrics(snapshot):
    with pytest.raises(AppError, match="Waluta"):
        calculate(snapshot.facts, goal(currency="EUR"), snapshot.spec)


def test_proxy_never_gets_purchase_roas(snapshot):
    proxy = goal(
        result_type="outbound_click",
        measurement_role="proxy",
        business_outcome="Sprzedaż biletów",
        result_label="Kliknięcie do operatora",
    )
    assert "roas" not in calculate(snapshot.facts, proxy, snapshot.spec)["metrics"]
    with pytest.raises(ValidationError):
        goal(result_type="outbound_click", measurement_role="proxy", value_action_type="purchase")


def test_purchase_value_and_roas(snapshot):
    for fact in snapshot.facts:
        fact.actions = {"purchase": 2}
        fact.action_values = {"purchase": 500}
    purchase = goal(
        result_type="purchase",
        action_type="purchase",
        value_action_type="purchase",
        targets={"roas": "4"},
    )
    row = calculate(snapshot.facts, purchase, snapshot.spec)
    assert row["metrics"]["roas"]["value"] == "5.000000"
    assert row["target_checks"]["roas"]["status"] == "met"


def test_assignment_effective_dates_do_not_mix_targets(snapshot, registry):
    registry.save_goal(goal(expected_revision=1, targets={"cost_per_result": "20"}))
    registry.assign(assignment(expected_revision=1, goal_revision=2, effective_from="2026-09-02"))
    rows = measurements(snapshot, snapshot.since, snapshot.until, registry.all())["groups"]
    assert len(rows) == 2
    assert rows[0]["totals"]["results"] == "14"
    assert rows[1]["totals"]["results"] == "28"
    assert rows[0]["target_checks"]["cost_per_result"]["status"] == "met"
    assert rows[1]["target_checks"]["cost_per_result"]["status"] == "missed"


def test_unassign_preserves_campaign_and_old_mapping(snapshot, registry):
    registry.assign(
        assignment(
            expected_revision=1, goal_id=None, goal_revision=None, effective_from="2026-09-02"
        )
    )
    result = measurements(snapshot, snapshot.since, snapshot.until, registry.all())
    assert result["groups"][0]["totals"]["results"] == "14"
    assert result["unmapped"][0]["days"] == 7
    with pytest.raises(AppError):
        registry.assign(assignment(expected_revision=2, effective_from=str(START)))


def test_duplicate_recommendation_retains_rejection(registry):
    registry.add_recommendation(recommendation())
    registry.event(event("reject", 1))
    duplicate = registry.add_recommendation(recommendation(recommendation_id="rec-duplicate"))
    assert duplicate["duplicate_of"] == "rec-1"
    assert duplicate["data"]["status"] == "rejected"
    with pytest.raises(AppError):
        registry.event(event("start", 2, effective_on="2026-09-02"))


def start(registry):
    registry.add_recommendation(recommendation())
    registry.event(event("accept", 1))
    return registry.event(event("start", 2, effective_on="2026-09-02"))


def test_start_is_not_meta_authorization_and_retries_are_idempotent(registry):
    row = start(registry)
    assert row["data"]["meta_write_authorized"] is False
    assert row["data"]["review_on"] == "2026-09-09"
    assert registry.event(event("start", 2, effective_on="2026-09-02"))["revision"] == 3
    assert len(registry.recommendations(date(2026, 9, 9), True)) == 1
    assert not registry.recommendations(date(2026, 9, 8), True)
    with pytest.raises(AppError):
        registry.event(event("note", 1))
    assert registry.get("recommendation", "rec-1")["revision"] == 3


def test_evaluation_uses_fixed_windows_and_saved_values(snapshot, registry):
    row = start(registry)
    result = evaluate("sync-test", snapshot, registry, row)
    assert result["outcome"] == "criterion_met"
    assert result["before"]["metrics"]["cost_per_result"]["value"] == "50.000000"
    assert result["after"]["metrics"]["cost_per_result"]["value"] == "25.000000"
    assert result["relative_changes"]["cost_per_result"]["value"] == "-50.000000"
    assert result["causal_effect_established"] is False
    saved = registry.save_evaluation("rec-1", 3, result)
    assert saved["data"]["status"] == "evaluated"
    assert registry.save_evaluation("rec-1", 3, result)["revision"] == 4
    assert not registry.recommendations(date(2026, 9, 10), True)


def test_incomplete_window_and_changed_mapping_block_evaluation(snapshot, registry):
    row = start(registry)
    short = snapshot.model_copy(deep=True)
    short.until = date(2026, 9, 7)
    with pytest.raises(AppError, match="okresy"):
        evaluate("sync-short", short, registry, row)
    registry.save_goal(goal(expected_revision=1, targets={"cost_per_result": "20"}))
    registry.assign(assignment(expected_revision=1, goal_revision=2, effective_from="2026-09-02"))
    with pytest.raises(AppError, match="Przypisanie"):
        evaluate("sync-new", snapshot, registry, row)
    assert registry.get("recommendation", "rec-1")["data"]["status"] == "running"


def test_small_sample_stays_inconclusive(snapshot, registry):
    raw = recommendation().model_dump(mode="json")
    raw["test_plan"]["minimum_results"] = "100"
    registry.add_recommendation(parse(Recommendation, raw))
    registry.event(event("accept", 1))
    row = registry.event(event("start", 2, effective_on="2026-09-02"))
    assert evaluate("sync-test", snapshot, registry, row)["outcome"] == "inconclusive"


def test_cli_report_and_replay_use_frozen_goal_and_history(tmp_path, snapshot, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "config/local"
    cfg.mkdir(parents=True)
    (cfg / "meta-client-a.json").write_text(
        json.dumps({"client_id": "client-a", "account_id": "act_123"})
    )
    with Store(Path("data/meta.sqlite3")) as store:
        snapshot_id = store.save_snapshot(snapshot)["run_id"]
    scope = ["--client", "client-a", "--account", "act_123"]
    for command, action, model in [
        ("goals", "set", goal()),
        ("goals", "assign", assignment()),
        ("recommendations", "add", recommendation()),
    ]:
        Path("input.json").write_text(model.model_dump_json())
        assert run([command, action, *scope, "--file", "input.json"]) == 0
        capsys.readouterr()
    assert (
        run(
            [
                "audit",
                *scope,
                "--since",
                str(START),
                "--until",
                "2026-09-08",
                "--snapshot",
                snapshot_id,
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)["data"]
    assert report["goal_measurements"]["groups"][0]["totals"]["results"] == "42"
    assert report["recommendation_history"][0]["data"]["status"] == "proposed"
    assert not any(r["code"] == "UNMAPPED_GOAL" for r in report["recommendations"])
    with Decisions(Path("data/decisions.sqlite3"), "client-a", "act_123") as registry:
        registry.event(event("reject", 1))
    assert run(["report", "show", *scope, "--run", report["run_id"]]) == 0
    assert json.loads(capsys.readouterr().out)["data"] == report
    assert (
        run(
            [
                "analyze",
                *scope,
                "--goal",
                "leads-form",
                "--since",
                "2026-09-02",
                "--until",
                "2026-09-08",
                "--snapshot",
                snapshot_id,
            ]
        )
        == 0
    )
    review = json.loads(capsys.readouterr().out)["data"]
    assert review["comparisons"][0]["relative_changes"]["cost_per_result"]["value"] == "-50.000000"
    assert review["recommendation_history"][0]["data"]["status"] == "rejected"


def test_followup_keeps_previous_rejection(registry):
    registry.add_recommendation(recommendation())
    registry.event(event("reject", 1))
    row = registry.add_recommendation(
        recommendation(
            recommendation_id="rec-2",
            followup_of="rec-1",
            followup_reason="Nowy zakres oferty pozwala wrócić do pomysłu.",
        )
    )
    assert row["id"] == "rec-2"
    assert row["data"]["status"] == "proposed"
    assert registry.get("recommendation", "rec-1")["data"]["status"] == "rejected"
    with pytest.raises(AppError):
        registry.add_recommendation(
            recommendation(
                recommendation_id="rec-3", followup_of="missing", followup_reason="Nowe dane."
            )
        )
    with pytest.raises(ValidationError):
        recommendation(followup_of="rec-2")


def test_foreign_records_cannot_enrich_snapshot(snapshot, registry):
    foreign = registry.all()
    foreign[0]["data"]["client_id"] = "someone-else"
    with pytest.raises(AppError, match="różnych klientów"):
        measurements(snapshot, snapshot.since, snapshot.until, foreign)


def test_threshold_cannot_hide_missing_baseline(snapshot, registry):
    raw = recommendation().model_dump(mode="json")
    raw["test_plan"]["minimum_results"] = None
    registry.add_recommendation(parse(Recommendation, raw))
    registry.event(event("accept", 1))
    row = registry.event(event("start", 2, effective_on="2026-09-02"))
    snapshot.facts[0].actions = {}
    assert evaluate("sync-test", snapshot, registry, row)["outcome"] == "inconclusive"


def test_two_connections_cannot_overwrite_decision(tmp_path, registry):
    registry.add_recommendation(recommendation())
    with Decisions(tmp_path / "decisions.sqlite3", "client-a", "act_123") as other:
        assert other.get("recommendation", "rec-1")["revision"] == 1
        registry.event(event("defer", 1, review_on="2026-09-15"))
        with pytest.raises(AppError):
            other.event(event("reject", 1))
        assert other.get("recommendation", "rec-1")["data"]["status"] == "deferred"
    assert not registry.recommendations(date(2026, 9, 14), True)
    assert registry.recommendations(date(2026, 9, 15), True)
    registry.event(event("cancel", 2))
    assert not registry.recommendations(date(2026, 9, 15), True)


def test_goal_review_and_pdf_keep_proxy_labels(snapshot, registry):
    from argparse import Namespace

    from meta_ads_manager.decision_cli import review_goal
    from meta_ads_manager.pdf_content import document_from_report

    registry.save_goal(
        goal(
            expected_revision=1,
            result_type="outbound_click",
            measurement_role="proxy",
            business_outcome="Sprzedaż biletów",
            result_label="Kliknięcie do sprzedawcy",
        )
    )
    registry.assign(assignment(expected_revision=1, goal_revision=2))
    registry.add_recommendation(recommendation(goal_revision=2))
    args = Namespace(
        since=date(2026, 9, 2), until=date(2026, 9, 8), last_days=None, goal="leads-form"
    )
    report = review_goal(args, "sync-test", snapshot, registry)
    doc = document_from_report(report)
    text = doc.model_dump_json()
    assert "sygnał pośredni" in text
    assert "Kliknięcie do sprzedawcy" in text
    assert "Historia rekomendacji" in text
    assert "ROAS" not in text
    assert "-50,00 %" in text
    assert "25,00 PLN" in text


def test_changed_goal_is_not_compared_as_same_goal(snapshot, registry):
    from argparse import Namespace

    from meta_ads_manager.decision_cli import review_goal

    registry.save_goal(goal(expected_revision=1, targets={"cost_per_result": "20"}))
    registry.assign(assignment(expected_revision=1, goal_revision=2, effective_from="2026-09-02"))
    result = review_goal(
        Namespace(
            since=date(2026, 9, 2), until=date(2026, 9, 8), last_days=None, goal="leads-form"
        ),
        "sync-test",
        snapshot,
        registry,
    )
    assert all(r["status"] == "not_comparable" for r in result["comparisons"])
    assert result["previous"][0]["goal_revision"] == 1
    assert result["current"][0]["goal_revision"] == 2
    from meta_ads_manager.pdf_content import document_from_report

    text = document_from_report(result).model_dump_json()
    assert "wersja 1" in text and "wersja 2" in text
    assert "50,00 PLN" in text and "20,00 PLN" in text
