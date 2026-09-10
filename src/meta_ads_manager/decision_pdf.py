"""Presentation of explicit goals and local decisions in saved PDF inputs."""

import json

from meta_ads_manager.pdf_content import metric_value, table, value
from meta_ads_manager.pdf_models import PdfDocument

STATUS = {
    "proposed": "Propozycja",
    "accepted": "Zaakceptowano pomysł",
    "rejected": "Odrzucono",
    "deferred": "Odłożono",
    "running": "Trwa ocena",
    "cancelled": "Zakończono bez oceny",
    "evaluated": "Oceniono",
}
METRICS = {"cost_per_result": "Koszt wyniku", "roas": "ROAS", "results": "Liczba wyników"}
OUTCOMES = {
    "criterion_met": "Spełniono kryterium",
    "criterion_not_met": "Nie spełniono kryterium",
    "inconclusive": "Brak rozstrzygnięcia",
}


def sections(report):
    result = []
    groups = report.get("goal_measurements", {}).get("groups", report.get("current", []))
    for group in groups:
        goal = group["goal_definition"]
        rows = [
            ["Wydatki", value(group["totals"]["spend"], goal["currency"])],
            [goal["result_label"], value(group["totals"]["results"])],
        ]
        rows += [
            [METRICS.get(key, key), metric_value(item)] for key, item in group["metrics"].items()
        ]
        for name, check in group["target_checks"].items():
            unit = "x" if name == "roas" else goal["currency"]
            state = {"met": "osiągnięty", "missed": "nieosiągnięty", "unavailable": "brak danych"}[
                check["status"]
            ]
            rows.append(["Cel: " + METRICS[name], f"{value(check['value'], unit)}; {state}"])
        section = table(
            f"{goal['name']} / wersja {group['goal_revision']}",
            ["Wskaźnik", "Wartość"],
            rows,
            [3, 2],
            [1],
        )
        role = {
            "primary": "wynik główny",
            "proxy": "sygnał pośredni",
            "diagnostic": "wskaźnik pomocniczy",
        }[goal["measurement_role"]]
        section["paragraphs"] = [
            f"Cel biznesowy: {goal['business_outcome']}. "
            f"Mierzymy: {goal['result_label']} ({role}).",
            f"Okres: {group['period']['since']} - {group['period']['until']}. "
            f"Kampanie: {', '.join(group['campaign_ids'])}.",
        ]
        if group["totals"]["results"] is None:
            section["paragraphs"].append(
                "W części dni brakuje wybranego zdarzenia. Sprawdź kompletność danych "
                "i definicję pomiaru, aby policzyć koszt wyniku za cały okres.",
            )
        result.append(section)
    for comparison in report.get("comparisons", []):
        if comparison["status"] != "comparable":
            result.append(
                {
                    "title": "Zmiana zakresu porównania",
                    "paragraphs": [
                        f"Wersja celu {comparison['goal_revision']}: zmieniło się przypisanie "
                        "kampanii lub okres jego obowiązywania. Wyniki pokazano osobno "
                        "dla poszczególnych wersji."
                    ],
                }
            )
            continue
        rows = []
        for name, change in comparison["relative_changes"].items():

            def observed(window, name=name):
                return (
                    value(window["totals"]["results"])
                    if name == "results"
                    else metric_value(window["metrics"][name])
                )

            rows.append(
                [
                    METRICS[name],
                    observed(comparison["previous"]),
                    observed(comparison["current"]),
                    metric_value(change),
                ]
            )
        result.append(
            table(
                "Porównanie okresów",
                ["Wskaźnik", "Poprzednio", "Obecnie", "Zmiana"],
                rows,
                [2, 1.5, 1.5, 1.5],
                [1, 2, 3],
            )
        )
    history = report.get("recommendation_history", [])
    if history:
        rows = []
        for row in history:
            data = row["data"]
            last = data["events"][-1] if data["events"] else {}
            evaluation = data.get("evaluation")
            note = (
                OUTCOMES[evaluation["outcome"]]
                if evaluation
                else last.get("reason", "Oczekuje na decyzję operatora.")
            )
            rows.append(
                [
                    data["definition"]["title"],
                    STATUS[data["status"]],
                    data.get("review_on") or "—",
                    note,
                ]
            )
        result.append(
            table(
                "Historia rekomendacji",
                ["Działanie", "Status", "Termin oceny", "Ostatnie ustalenie"],
                rows,
                [2.5, 1.5, 1.2, 2.5],
            )
        )
    return result


def review_document(report):
    period, previous, spec = report["period"], report["previous_period"], report["report_spec"]
    content = sections(report)
    if any(item["status"] != "comparable" for item in report["comparisons"]):
        content += [{"title": "Wyniki poprzedniego okresu"}]
        content += sections({"current": report["previous"]})
    raw = {
        "client_id": report["client_id"],
        "account_id": report["account_id"],
        "title": "Analiza realizacji celu",
        "subtitle": report["goal_id"],
        "source": report["source"],
        "report_date": report["generated_at"][:10],
        "period_since": period["since"],
        "period_until": period["until"],
        "currency": spec["currency"],
        "timezone": spec["timezone"],
        "coverage": "report",
        "summary": [f"Wyniki porównujemy z okresem {previous['since']} – {previous['until']}."],
        "sections": content,
        "limitations": [
            "Porównanie obejmuje wyniki zapisane w wybranym snapshotcie i kampanie "
            "przypisane do wskazanych wersji celu."
        ],
        "evidence": [
            f"Raport: {report['run_id']}",
            f"Snapshot: {report['snapshot_id']}",
            f"Pobrano dane: {report['data_fetched_at']}",
            f"Atrybucja: {spec['attribution']}; czas wyniku: {spec['action_report_time']}",
            f"Wersja kodu: {report['code_version']}",
        ],
    }
    return PdfDocument.model_validate_json(json.dumps(raw))
