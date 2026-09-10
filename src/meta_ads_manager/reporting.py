"""Account reports and evidence-backed audit input for a conversational agent."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from meta_ads_manager import __version__
from meta_ads_manager.analytics import aggregate, number
from meta_ads_manager.analytics import metric as ratio_metric
from meta_ads_manager.errors import AppError
from meta_ads_manager.models import ClientProfile, Snapshot


def account_report(
    snapshot_id: str, snapshot: Snapshot, profile: ClientProfile, since: date, until: date
) -> dict:
    if profile.client_id != snapshot.client_id:
        raise AppError("SCOPE_MISMATCH", "Profil nie należy do klienta snapshotu.", 3)
    if not any(a.account_id == snapshot.account_id for a in profile.accounts):
        raise AppError("SCOPE_MISMATCH", "Snapshot nie należy do konta klienta.", 3)
    if since > until:
        raise AppError("VALIDATION_ERROR", "Początek okresu wypada po jego końcu.", 2)
    if since < snapshot.since or until > snapshot.until:
        raise AppError("INSUFFICIENT_DATA", "Snapshot nie obejmuje całego żądanego okresu.", 6)
    goals = {
        g.goal_id: g
        for p in profile.projects
        if snapshot.account_id in p.account_ids
        for g in p.goal_profiles
    }
    facts = [f for f in snapshot.facts if since <= f.day <= until]
    currency = snapshot.spec.currency

    def common_totals(selected):
        result = aggregate(selected, "lead_generation", currency)
        if not selected and snapshot.source == "meta":
            return {
                "totals": {"spend": "0", "impressions": 0, "link_clicks": 0},
                "metrics": {
                    "cpm": ratio_metric(0, 0, currency, 1000),
                    "link_ctr": ratio_metric(0, 0, "percent", 100),
                    "link_cpc": ratio_metric(0, 0, currency),
                },
            }
        # Account-wide conversions/ROAS would mix different business outcomes.
        return {
            "totals": {k: result["totals"][k] for k in ("spend", "impressions", "link_clicks")},
            "metrics": {k: result["metrics"][k] for k in ("cpm", "link_ctr", "link_cpc")},
        }

    def actions(selected, field):
        totals = {}
        for fact in selected:
            for key, value in getattr(fact, field).items():
                totals[key] = totals.get(key, Decimal(0)) + value
        return {key: number(value) for key, value in sorted(totals.items())}

    rows = []
    for campaign in snapshot.campaigns:
        goal = goals.get(campaign.goal_id)
        selected = [f for f in facts if f.campaign_id == campaign.campaign_id]
        rows.append(
            {
                "campaign_id": campaign.campaign_id,
                "name": campaign.name,
                "status_at_snapshot": campaign.status,
                "objective": campaign.objective,
                "goal_id": campaign.goal_id,
                "goal_type": goal.type if goal else None,
                "measurement_status": "mapped" if goal else "unmapped",
                **(
                    {
                        "reported_actions": actions(selected, "actions"),
                        "reported_action_values": actions(selected, "action_values"),
                        "days_without_insight_row": sum(f.inferred_no_delivery for f in selected),
                    }
                    if snapshot.source == "meta"
                    else {}
                ),
                **(aggregate(selected, goal.type, currency) if goal else common_totals(selected)),
            }
        )
    groups = []
    for goal_id, goal in goals.items():
        ids = {c.campaign_id for c in snapshot.campaigns if c.goal_id == goal_id}
        if ids:
            groups.append(
                {
                    "goal_id": goal_id,
                    "goal_type": goal.type,
                    "goal_profile": goal.model_dump(mode="json"),
                    "campaign_count": len(ids),
                    **aggregate([f for f in facts if f.campaign_id in ids], goal.type, currency),
                }
            )
    return {
        "schema_version": "1.0",
        "kind": "campaign_report",
        "run_id": f"report_{uuid4().hex}",
        "snapshot_id": snapshot_id,
        "client_id": snapshot.client_id,
        "account_id": snapshot.account_id,
        "source": snapshot.source,
        **(
            {
                "account_name": snapshot.meta.account_name,
                "snapshot_verification": snapshot.meta.model_dump(mode="json"),
            }
            if snapshot.meta
            else {}
        ),
        "status": "SUCCEEDED",
        "code_version": __version__,
        "generated_at": datetime.now(UTC).isoformat(),
        "data_fetched_at": snapshot.fetched_at.isoformat(),
        "period": {"since": since.isoformat(), "until": until.isoformat()},
        "report_spec": snapshot.spec.model_dump(mode="json"),
        "campaign_count": len(rows),
        "summary": common_totals(facts),
        "goal_groups": groups,
        "campaigns": rows,
        "evidence_refs": [snapshot_id],
        "limitations": (
            [
                "Dane syntetyczne. Okres demo jest zakotwiczony w dostępnych danych, nie w dziś.",
                "Wszystkie kampanie oznacza kompletną listę w tym snapshotcie demonstracyjnym.",
            ]
            if snapshot.source == "demo"
            else [
                "Dane Meta API; lista obejmuje kampanie dostępne tokenowi, także wstrzymane, "
                "archiwalne oraz kampanie obecne w Insights. Meta nie udostępnia na liście "
                "usuniętych obiektów; bez wyników w okresie mogą być pominięte.",
                "Zera emisji dla brakujących dni uzupełniono po pobraniu wszystkich stron "
                "i uzgodnieniu sum z podsumowaniem konta. Nie potwierdzają sprawności pomiaru.",
                "Atrybucja: 7 dni po kliknięciu i 1 dzień po wyświetleniu; czas raportowania: "
                "wyświetlenie. Ustawienia widoku Ads Manager mogą być inne.",
                "Typy reported_actions mogą się nakładać. Nie sumuj ich jako konwersji. "
                "CPL/CPA/ROAS wymagają uzgodnionego mapowania zdarzeń i celów.",
                "Dane mogą zostać zaktualizowane przez Metę po pobraniu. "
                "snapshot_verification dotyczy całego okresu snapshotu.",
            ]
        )
        + [
            "Konwersje i koszty wyniku agregowane osobno dla każdego celu biznesowego.",
            "Status kampanii dotyczy snapshotu; nie opisuje całej historii emisji.",
        ],
    }


def account_audit(report: dict) -> dict:
    """Return bounded recommendations, never a simulated full live Meta audit."""
    recommendations = []

    def add(code, priority, observation, action, evidence, campaign_id=None):
        recommendations.append(
            {
                "code": code,
                "priority": priority,
                "campaign_id": campaign_id,
                "observation": observation,
                "suggested_action": action,
                "evidence": evidence,
                "evidence_refs": report["evidence_refs"],
                "execution": "recommendation_only",
                "confidence": "descriptive",
            }
        )

    by_goal = {g["goal_id"]: g for g in report["goal_groups"]}
    if report["summary"]["totals"]["spend"] == "0" or (
        report["summary"]["totals"]["spend"] is not None
        and Decimal(report["summary"]["totals"]["spend"]) == 0
    ):
        add(
            "NO_SPEND",
            "low",
            "W wybranym okresie konto nie miało wydatków.",
            "Do oceny skuteczności wybierz okres z emisją. Sam brak wydatków "
            "nie oznacza problemu z kontem.",
            report["summary"]["totals"],
        )
    for row in report["campaigns"]:
        if row["measurement_status"] == "unmapped":
            if row["totals"]["spend"] is not None and Decimal(row["totals"]["spend"]) == 0:
                continue
            add(
                "UNMAPPED_GOAL",
                "high",
                "Kampania nie ma rozpoznanego celu biznesowego.",
                "Przypisz profil celu przed oceną kosztu wyniku.",
                {"goal_id": row["goal_id"]},
                row["campaign_id"],
            )
            continue
        spend = Decimal(row["totals"]["spend"])
        conversions = row["totals"]["conversions"]
        if conversions is None or (Decimal(conversions) == 0 and spend > 0):
            add(
                "CHECK_CONVERSION_DATA",
                "high",
                "Brak pomiaru konwersji lub wydatki bez konwersji.",
                "Sprawdź zdarzenie konwersji, kompletność pomiaru i opóźnienia raportowania; "
                "same te dane nie dowodzą awarii ani nie uzasadniają wyłączenia kampanii.",
                {"spend": number(spend), "conversions": conversions},
                row["campaign_id"],
            )
        goal = by_goal[row["goal_id"]]["goal_profile"]
        for metric, target in goal["target_metrics"].items():
            observed = row["metrics"][metric]["value"]
            if target is None or observed is None:
                continue
            misses = (
                Decimal(observed) < Decimal(target)
                if metric == "roas"
                else (Decimal(observed) > Decimal(target))
            )
            if misses:
                add(
                    "TARGET_MISSED",
                    "medium",
                    "Wynik kampanii nie spełnia zapisanego celu.",
                    "Sprawdź skalę danych, atrybucję, ostatnie zmiany i lejek; następnie "
                    "zaprojektuj test. Nie zmieniaj budżetu wyłącznie "
                    "na podstawie tego porównania.",
                    {
                        "metric": metric,
                        "observed": observed,
                        "target": target,
                        "conversions": conversions,
                    },
                    row["campaign_id"],
                )

    for group in report["goal_groups"]:
        targets = group["goal_profile"]["target_metrics"]
        if all(value is None for value in targets.values()):
            add(
                "MISSING_TARGET",
                "medium",
                "Profil nie ma uzgodnionych progów wyniku.",
                "Ustal docelowy koszt lub zwrot zgodnie z ekonomią oferty.",
                {"goal_id": group["goal_id"], "target_metrics": targets},
            )
        if group["goal_type"] == "lead_generation":
            action = "Dołącz agregaty kwalifikacji i sprzedaży z CRM, aby ocenić jakość leadów."
        else:
            action = "Dołącz dane sklepu o marży i zwrotach, aby ocenić rentowność sprzedaży."
        add(
            "BUSINESS_DATA_UNAVAILABLE",
            "medium",
            "Snapshot nie zawiera danych biznesowych.",
            action,
            {"goal_id": group["goal_id"], "source": "not_connected"},
        )

    order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(key=lambda item: order[item["priority"]])
    return {
        **report,
        "kind": "account_audit",
        "run_id": f"audit_{uuid4().hex}",
        "status": "PARTIAL",
        "coverage": [
            {
                "area": "campaign_inventory",
                "status": "checked",
                "detail": "Lista kampanii w snapshotcie, przypisanie celu i status przy pobraniu.",
            },
            {
                "area": "reported_performance",
                "status": "checked",
                "detail": "Metryki emisji za żądany okres; porównanie celów, jeśli są zapisane.",
            },
            *(
                [
                    {
                        "area": "goal_mapping",
                        "status": "unavailable",
                        "detail": "Brak uzgodnionego mapowania zdarzeń i celów biznesowych Meta.",
                    }
                ]
                if report["source"] == "meta"
                else []
            ),
            *[
                {"area": area, "status": "unavailable", "detail": reason}
                for area, reason in [
                    ("tracking", "Brak konfiguracji źródeł zdarzeń i diagnostyki pomiaru."),
                    ("targeting", "Brak konfiguracji zestawów reklam i grup odbiorców."),
                    ("creative", "Brak treści i materiałów reklamowych."),
                    ("budget_and_delivery", "Brak budżetów, harmonogramów i diagnostyki emisji."),
                    ("change_history", "Brak historii zmian do interpretacji przyczyn wyników."),
                    ("business_outcomes", "Brak danych CRM/sklepu."),
                ]
            ],
        ],
        "recommendations": recommendations,
        "limitations": report["limitations"]
        + [
            "Audyt częściowy. Niesprawdzonych obszarów nie uznawaj za poprawne.",
            "Przekroczenie progu jest obserwacją, nie diagnozą przyczyny lub testem istotności.",
        ],
    }
