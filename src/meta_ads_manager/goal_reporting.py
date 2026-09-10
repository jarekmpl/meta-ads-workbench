"""Deterministic event mapping and comparisons; original snapshots remain unchanged."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from meta_ads_manager.analytics import metric, number
from meta_ads_manager.decision_models import BusinessGoal
from meta_ads_manager.decision_store import canonical, fail


def goal_definitions(records):
    return {
        (r["id"], r["revision"]): BusinessGoal.model_validate_json(canonical(r["data"]))
        for r in records
        if r["category"] == "goal"
    }


def scoped_records(snapshot, records):
    for row in records:
        payload = row["data"]
        if row["category"] == "recommendation":
            payload = payload["definition"]
        if (payload.get("client_id"), payload.get("account_id")) != (
            snapshot.client_id,
            snapshot.account_id,
        ):
            fail("SCOPE_MISMATCH", "Rejestr i snapshot dotyczą różnych klientów lub kont.")


def assignment_at(records, campaign, day):
    eligible = [
        r
        for r in records
        if r["category"] == "assignment"
        and r["id"] == campaign
        and date.fromisoformat(r["data"]["effective_from"]) <= day
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda r: (r["data"]["effective_from"], r["revision"]))


def calculate(facts, goal, spec):
    if (goal.currency, goal.attribution, goal.action_report_time) != (
        spec.currency,
        spec.attribution,
        spec.action_report_time,
    ):
        fail("GOAL_INCOMPATIBLE", "Waluta lub atrybucja celu nie pasuje do snapshotu.")
    spend = sum((f.spend for f in facts), Decimal(0))

    def total(field, key):
        if key is None or not facts:
            return None, None, 0
        values = [getattr(f, field).get(key) for f in facts]
        missing = sum(v is None for v in values)
        reported = sum((v for v in values if v is not None), Decimal(0))
        value = None if missing and goal.missing_action_policy == "unknown" else reported
        return value, reported, missing

    count, reported, missing = total("actions", goal.action_type)
    value, reported_value, missing_value = total("action_values", goal.value_action_type)
    metrics = {"cost_per_result": metric(spend if facts else None, count, spec.currency)}
    if goal.value_action_type:
        metrics["roas"] = metric(value, spend if facts else None, "ratio")
    targets = {}
    for name, target in goal.targets.model_dump().items():
        if target is None:
            continue
        observed = metrics.get(name, {}).get("value")
        state = "unavailable"
        if observed is not None:
            met = Decimal(observed) >= target if name == "roas" else Decimal(observed) <= target
            state = "met" if met else "missed"
        targets[name] = {"value": number(target), "observed": observed, "status": state}
    return {
        "totals": {
            "spend": number(spend),
            "results": number(count) if count is not None else None,
            "result_value": number(value) if value is not None else None,
            "reported_results": number(reported) if reported is not None else None,
            "reported_result_value": number(reported_value) if reported_value is not None else None,
        },
        "metrics": metrics,
        "target_checks": targets,
        "coverage": {
            "campaign_days": len(facts),
            "days_without_action": missing,
            "days_without_value": missing_value,
            "inferred_no_delivery_days": sum(f.inferred_no_delivery for f in facts),
            "missing_action_policy": goal.missing_action_policy,
        },
    }


def measurements(snapshot, since, until, records):
    scoped_records(snapshot, records)
    if snapshot.source != "meta":
        fail("SOURCE_MISMATCH", "Rejestr celów dotyczy danych Meta.")
    if since > until or since < snapshot.since or until > snapshot.until:
        fail("INSUFFICIENT_DATA", "Snapshot nie obejmuje całego żądanego okresu.")
    definitions = goal_definitions(records)
    selected = [f for f in snapshot.facts if since <= f.day <= until]
    groups, entries, unmapped = defaultdict(list), defaultdict(list), defaultdict(list)
    used = set()
    for fact in selected:
        assignment = assignment_at(records, fact.campaign_id, fact.day)
        if assignment is None or assignment["data"]["goal_id"] is None:
            unmapped[fact.campaign_id].append(fact)
            continue
        binding = assignment["data"]
        key = (binding["goal_id"], binding["goal_revision"])
        if key not in definitions:
            fail("GOAL_REQUIRED", "Przypisanie wskazuje nieistniejącą wersję celu.")
        groups[key].append(fact)
        entries[(fact.campaign_id, *key)].append(fact)
        used.add((assignment["id"], assignment["revision"]))

    def describe(key, facts):
        goal = definitions[key]
        return {
            "goal_id": key[0],
            "goal_revision": key[1],
            "goal_definition": goal.model_dump(mode="json"),
            "campaign_ids": sorted({f.campaign_id for f in facts}),
            "period": {
                "since": str(min(f.day for f in facts)),
                "until": str(max(f.day for f in facts)),
            },
            **calculate(facts, goal, snapshot.spec),
        }

    return {
        "period": {"since": str(since), "until": str(until)},
        "groups": [describe(key, facts) for key, facts in sorted(groups.items())],
        "campaigns": [
            {"campaign_id": campaign, **describe((goal, rev), facts)}
            for (campaign, goal, rev), facts in sorted(entries.items())
        ],
        "unmapped": [
            {
                "campaign_id": campaign,
                "days": len(facts),
                "spend": number(sum((f.spend for f in facts), Decimal(0))),
            }
            for campaign, facts in sorted(unmapped.items())
        ],
        "assignment_versions": [
            {"campaign_id": identifier, "revision": revision}
            for identifier, revision in sorted(used)
        ],
    }


def enrich_report(report, snapshot, since, until, registry):
    records = registry.all()
    report["goal_measurements"] = measurements(snapshot, since, until, records)
    report["recommendation_history"] = registry.recommendations()
    report["recommendation_history_as_of"] = str(date.today())
    mapped = {r["campaign_id"] for r in report["goal_measurements"]["campaigns"]}
    unmapped = {r["campaign_id"] for r in report["goal_measurements"]["unmapped"]}
    for row in report["campaigns"]:
        identifier = row["campaign_id"]
        row["business_goal_status"] = (
            "partial"
            if identifier in mapped and identifier in unmapped
            else "mapped"
            if identifier in mapped
            else "unmapped"
        )
    return report


def enrich_audit(audit):
    measurement = audit["goal_measurements"]
    unmapped = {item["campaign_id"] for item in measurement["unmapped"]}
    audit["recommendations"] = [
        r
        for r in audit["recommendations"]
        if r["code"] != "UNMAPPED_GOAL" or r["campaign_id"] in unmapped
    ]
    history = audit["recommendation_history"]
    for row in measurement["campaigns"]:
        goal = row["goal_definition"]
        for name, check in row["target_checks"].items():
            if check["status"] != "missed":
                continue
            audit["recommendations"].append(
                {
                    "code": "TARGET_MISSED",
                    "priority": "medium",
                    "campaign_id": row["campaign_id"],
                    "observation": f"{goal['result_label']}: {name} = {check['observed']}; "
                    f"cel {check['value']}.",
                    "suggested_action": "Sprawdź wcześniejsze decyzje i porównywalne reklamy tej "
                    "kampanii, aby wybrać następny test.",
                    "evidence": {
                        "goal_id": row["goal_id"],
                        "goal_revision": row["goal_revision"],
                        **check,
                        "metric": name,
                        "totals": row["totals"],
                    },
                    "evidence_refs": audit["evidence_refs"],
                    "execution": "recommendation_only",
                    "confidence": "descriptive",
                }
            )
    for item in audit["recommendations"]:
        item["related_recommendation_ids"] = [
            r["id"]
            for r in history
            if item.get("campaign_id") in r["data"]["definition"]["campaign_ids"]
        ]
    for area in audit["coverage"]:
        if area["area"] == "goal_mapping":
            area.update(
                status="partial" if unmapped else "checked",
                detail="Wersjonowane przypisania celów; braki wskazano w goal_measurements.",
            )
    audit["recommendations"].sort(key=lambda r: {"high": 0, "medium": 1, "low": 2}[r["priority"]])
    return audit


def fixed_window(snapshot, records, goal_id, goal_revision, campaigns, since, until):
    scoped_records(snapshot, records)
    if snapshot.source != "meta":
        fail("SOURCE_MISMATCH", "Ocena wymaga snapshotu Meta.")
    if since > until or since < snapshot.since or until > snapshot.until:
        fail("INSUFFICIENT_DATA", "Pobierz snapshot obejmujący pełne oba okresy oceny.")
    if not set(campaigns).issubset({c.campaign_id for c in snapshot.campaigns}):
        fail("INSUFFICIENT_DATA", "Brak kampanii objętej oceną w snapshotcie.")
    facts = [f for f in snapshot.facts if f.campaign_id in campaigns and since <= f.day <= until]
    for fact in facts:
        row = assignment_at(records, fact.campaign_id, fact.day)
        if row is None or (row["data"]["goal_id"], row["data"]["goal_revision"]) != (
            goal_id,
            goal_revision,
        ):
            fail("GOAL_CHANGED", "Przypisanie lub wersja celu różni się w okresie porównania.")
    goal = goal_definitions(records).get((goal_id, goal_revision))
    if goal is None:
        fail("GOAL_REQUIRED", "Brak zapisanej wersji celu.")
    return {
        "period": {"since": str(since), "until": str(until)},
        **calculate(facts, goal, snapshot.spec),
    }


def compare(before, after):
    changes = {}
    for name in after["metrics"]:
        a = after["metrics"][name]["value"]
        b = before["metrics"][name]["value"]
        changes[name] = metric(
            Decimal(a) - Decimal(b) if a is not None and b is not None else None,
            Decimal(b) if b is not None else None,
            "percent",
            100,
        )
    a, b = after["totals"]["results"], before["totals"]["results"]
    changes["results"] = metric(
        Decimal(a) - Decimal(b) if a is not None and b is not None else None,
        Decimal(b) if b is not None else None,
        "percent",
        100,
    )
    return changes


def evaluate(snapshot_id, snapshot, registry, row):
    data = row["data"]
    if data["status"] != "running":
        fail("INVALID_TRANSITION", "Do oceny potrzebny jest rozpoczęty test.")
    definition, records = data["definition"], registry.all()
    plan = definition["test_plan"]
    since = date.fromisoformat(data["started_on"])
    until = since + timedelta(days=plan["evaluation_days"] - 1)
    common = (
        snapshot,
        records,
        definition["goal_id"],
        definition["goal_revision"],
        definition["campaign_ids"],
    )
    baseline = plan["baseline"]
    before = fixed_window(
        *common, date.fromisoformat(baseline["since"]), date.fromisoformat(baseline["until"])
    )
    after = fixed_window(*common, since, until)
    name = plan["metric"]

    def observed(window):
        return (
            window["totals"]["results"] if name == "results" else window["metrics"][name]["value"]
        )

    previous, current = observed(before), observed(after)
    threshold = plan["success_threshold"]
    reference = threshold if threshold is not None else previous
    enough = True
    if plan["minimum_results"] is not None:
        enough = all(
            w["totals"]["results"] is not None
            and Decimal(w["totals"]["results"]) >= Decimal(plan["minimum_results"])
            for w in (before, after)
        )
    outcome = "inconclusive"
    if enough and reference is not None and current is not None and previous is not None:
        a, b = Decimal(current), Decimal(reference)
        met = (
            (a <= b if plan["direction"] == "decrease" else a >= b)
            if threshold is not None
            else (a < b if plan["direction"] == "decrease" else a > b)
        )
        outcome = "criterion_met" if met else "criterion_not_met"
    return {
        "snapshot_id": snapshot_id,
        "goal_id": definition["goal_id"],
        "goal_revision": definition["goal_revision"],
        "campaign_ids": definition["campaign_ids"],
        "method": plan["method"],
        "outcome": outcome,
        "metric": name,
        "reference": reference,
        "criterion": "absolute_threshold" if threshold is not None else "improvement_from_baseline",
        "minimum_results_met": enough,
        "before": before,
        "after": after,
        "relative_changes": compare(before, after),
        "causal_effect_established": False,
    }
