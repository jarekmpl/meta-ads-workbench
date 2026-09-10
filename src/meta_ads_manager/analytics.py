from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from uuid import uuid4

from meta_ads_manager import __version__
from meta_ads_manager.errors import AppError
from meta_ads_manager.models import Fact, Goal, Snapshot


def number(value: Decimal | int) -> str:
    return format(Decimal(value), "f")


def metric(
    numerator: Decimal | int | None,
    denominator: Decimal | int | None,
    unit: str,
    multiplier: int = 1,
) -> dict:
    reason = None
    value = None
    if numerator is None or denominator is None:
        reason = "unavailable"
    elif denominator == 0:
        reason = "zero_denominator"
    else:
        with localcontext() as ctx:
            ctx.prec = 50
            value = number(
                (Decimal(numerator) / Decimal(denominator) * multiplier).quantize(
                    Decimal("0.000001")
                )
            )
    return {"value": value, "unit": unit, "reason": reason}


def aggregate(facts: list[Fact], goal_type: str, currency: str) -> dict:
    def total(field: str):
        values = [getattr(fact, field) for fact in facts]
        if not values or any(value is None for value in values):
            return None
        return sum(values, Decimal(0))

    spend = total("spend")
    impressions = total("impressions")
    clicks = total("link_clicks")
    conversions = total("conversions")
    value = total("conversion_value")
    metrics = {
        "cpm": metric(spend, impressions, currency, 1000),
        "link_ctr": metric(clicks, impressions, "percent", 100),
        "link_cpc": metric(spend, clicks, currency),
        "cpl" if goal_type == "lead_generation" else "cpa": metric(spend, conversions, currency),
        "reach": {"value": None, "unit": "people", "reason": "non_additive_unavailable"},
        "frequency": {"value": None, "unit": "ratio", "reason": "non_additive_unavailable"},
    }
    if goal_type == "ecommerce":
        metrics["roas"] = metric(value, spend, "ratio")
        metrics["average_purchase_value"] = metric(value, conversions, currency)
    else:
        metrics["cpql"] = {"value": None, "unit": currency, "reason": "unavailable"}
    return {
        "totals": {
            "spend": number(spend) if spend is not None else None,
            "impressions": int(impressions) if impressions is not None else None,
            "link_clicks": int(clicks) if clicks is not None else None,
            "conversions": number(conversions) if conversions is not None else None,
            "conversion_value": number(value) if value is not None else None,
        },
        "metrics": metrics,
    }


def weekly_review(snapshot_id: str, snapshot: Snapshot, goal: Goal) -> dict:
    previous_start = snapshot.until - timedelta(days=13)
    current_start = snapshot.until - timedelta(days=6)
    if snapshot.since > previous_start:
        raise AppError("INSUFFICIENT_DATA", "Porównanie tygodni wymaga 14 pełnych dni.", 6)
    campaigns = [c for c in snapshot.campaigns if c.goal_id == goal.goal_id]
    if not campaigns:
        raise AppError("INSUFFICIENT_DATA", "Brak kampanii przypisanych do wybranego celu.", 6)
    currency = snapshot.spec.currency

    def comparison(ids: set[str]) -> dict:
        selected = [f for f in snapshot.facts if f.campaign_id in ids]
        previous = aggregate(
            [f for f in selected if previous_start <= f.day < current_start], goal.type, currency
        )
        current = aggregate([f for f in selected if f.day >= current_start], goal.type, currency)
        changes = {}
        for name in current["metrics"]:
            before = previous["metrics"][name]["value"]
            after = current["metrics"][name]["value"]
            changes[name] = metric(
                Decimal(after) - Decimal(before)
                if after is not None and before is not None
                else None,
                Decimal(before) if before is not None else None,
                "percent",
                100,
            )
        return {"previous": previous, "current": current, "relative_changes": changes}

    summary = comparison({c.campaign_id for c in campaigns})
    target_checks = {}
    for key, target in goal.target_metrics.model_dump().items():
        observed = summary["current"]["metrics"][key]["value"]
        if target is None or observed is None:
            status = "unavailable"
        else:
            meets = Decimal(observed) >= target if key == "roas" else Decimal(observed) <= target
            status = "met" if meets else "not_met"
        target_checks[key] = {
            "target": number(target) if target is not None else None,
            "observed": observed,
            "status": status,
        }
    return {
        "schema_version": "1.0",
        "kind": "analysis_report",
        "run_id": f"analysis_{uuid4().hex}",
        "snapshot_id": snapshot_id,
        "client_id": snapshot.client_id,
        "account_id": snapshot.account_id,
        "goal_id": goal.goal_id,
        "goal_profile": goal.model_dump(mode="json"),
        "source": snapshot.source,
        "status": "SUCCEEDED",
        "recipe": "weekly-review",
        "recipe_version": "1",
        "code_version": __version__,
        "generated_at": datetime.now(UTC).isoformat(),
        "data_fetched_at": snapshot.fetched_at.isoformat(),
        "report_spec": snapshot.spec.model_dump(mode="json"),
        "periods": {
            "previous": {
                "since": previous_start.isoformat(),
                "until": (current_start - timedelta(days=1)).isoformat(),
            },
            "current": {"since": current_start.isoformat(), "until": snapshot.until.isoformat()},
        },
        "summary": summary,
        "target_checks": target_checks,
        "campaigns": [
            {"campaign_id": c.campaign_id, "name": c.name, **comparison({c.campaign_id})}
            for c in campaigns
        ],
        "evidence_refs": [snapshot_id],
        "recommendations": [],
        "limitations": [
            "Dane syntetyczne; daty odnoszą się do stałego okresu demonstracyjnego.",
            "Porównanie opisowe; nie dowodzi przyczynowości ani istotności statystycznej.",
            "Brak integracji CRM i sklepu: jakość leadów, marża i rentowność są niedostępne.",
            "Ocena celu jest arytmetyczna; nie stanowi rekomendacji zmiany budżetu.",
        ],
    }
