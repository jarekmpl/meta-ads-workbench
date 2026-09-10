"""Map saved reports to a presentation model without fetching or changing source data."""

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from meta_ads_manager.errors import AppError
from meta_ads_manager.pdf_models import PdfDocument, PdfNotes

LABELS = {
    "spend": "Wydatki",
    "impressions": "Wyświetlenia",
    "link_clicks": "Kliknięcia linku",
    "conversions": "Wyniki",
    "conversion_value": "Wartość wyników",
    "cpm": "CPM",
    "link_ctr": "CTR linku",
    "link_cpc": "CPC linku",
    "cpl": "CPL",
    "cpa": "CPA",
    "roas": "ROAS",
    "cpql": "CPQL",
    "reach": "Zasięg",
    "frequency": "Częstotliwość",
    "average_purchase_value": "Średnia wartość zakupu",
    "campaign_inventory": "Lista kampanii",
    "reported_performance": "Wyniki emisji",
    "tracking": "Pomiar",
    "targeting": "Odbiorcy",
    "creative": "Kreacje",
    "budget_and_delivery": "Budżety i emisja",
    "change_history": "Historia zmian",
    "business_outcomes": "Wyniki biznesowe",
    "goal_mapping": "Mapowanie celów",
}
STATUSES = {"checked": "Sprawdzono", "unavailable": "Brak danych", "partial": "Częściowo"}
GOALS = {"lead_generation": "Pozyskiwanie leadów", "ecommerce": "Sprzedaż"}


def value(number, unit=None) -> str:
    if number is None:
        return "brak danych"
    try:
        result = Decimal(str(number))
    except InvalidOperation:
        raise AppError("PDF_INPUT", "Niepoprawna wartość liczbowa w raporcie.", 2) from None
    if not result.is_finite():
        raise AppError("PDF_INPUT", "Niepoprawna wartość liczbowa w raporcie.", 2)
    places = 2 if unit else (0 if result == result.to_integral_value() else 2)
    rendered = f"{result:,.{places}f}".replace(",", " ").replace(".", ",")
    return rendered + (f" {unit}" if unit else "")


def metric_value(metric) -> str:
    unit = metric.get("unit")
    suffix = "%" if unit == "percent" else ("x" if unit == "ratio" else unit)
    return value(metric.get("value"), suffix)


def table(title, columns, rows, widths=None, numeric_columns=None):
    return {
        "title": title,
        "table": {
            "columns": columns,
            "rows": rows,
            "widths": widths,
            "numeric_columns": numeric_columns or [],
        },
    }


def load_json(path: Path) -> dict:
    from meta_ads_manager.cli import no_duplicate_keys

    raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicate_keys)
    if isinstance(raw, dict) and "ok" in raw:
        if raw["ok"] is not True:
            raise AppError("PDF_INPUT", "Nie można eksportować nieudanego raportu.", 2)
        raw = raw.get("data")
    if not isinstance(raw, dict):
        raise AppError("PDF_INPUT", "PDF wymaga obiektu JSON.", 2)
    return raw


def document_from_report(report: dict) -> PdfDocument:
    kind = report.get("kind")
    if kind == "pdf_document":
        return PdfDocument.model_validate_json(json.dumps(report))
    if kind not in ("campaign_report", "account_audit", "analysis_report"):
        raise AppError("PDF_INPUT", "Nieobsługiwany rodzaj raportu PDF.", 2)
    if report.get("schema_version") != "1.0":
        raise AppError("PDF_INPUT", "Nieobsługiwana wersja raportu.", 2)
    if report.get("status") not in ("SUCCEEDED", "PARTIAL"):
        raise AppError("PDF_INPUT", "Raport nie jest gotowy do eksportu.", 2)
    try:
        weekly = kind == "analysis_report"
        period = report["periods"]["current"] if weekly else report["period"]
        currency = report["report_spec"]["currency"]
        totals = report["summary"]["current"]["totals"] if weekly else report["summary"]["totals"]
        doc = {
            "client_id": report["client_id"],
            "account_id": report["account_id"],
            "title": {
                "campaign_report": "Raport kampanii",
                "account_audit": "Audyt konta",
                "analysis_report": "Analiza tygodniowa",
            }[kind],
            "subtitle": report.get("account_name", report["client_id"]),
            "source": report["source"],
            "report_date": report["generated_at"][:10],
            "period_since": period["since"],
            "period_until": period["until"],
            "currency": currency,
            "timezone": report["report_spec"]["timezone"],
            "coverage": "partial" if report["status"] == "PARTIAL" else "report",
            "summary": [],
            "metrics": [
                {"label": "Wydatki", "value": value(totals["spend"], currency)},
                {"label": "Wyświetlenia", "value": value(totals["impressions"])},
                {"label": "Kliknięcia linku", "value": value(totals["link_clicks"])},
            ],
            "sections": [],
            "limitations": report["limitations"],
            "evidence": [
                f"Raport: {report['run_id']}",
                f"Snapshot: {report['snapshot_id']}",
                f"Pobrano dane: {report['data_fetched_at']}",
                f"Wygenerowano raport: {report['generated_at']}",
                f"Atrybucja: {report['report_spec']['attribution']}; "
                f"czas wyniku: {report['report_spec']['action_report_time']}",
                f"Wersja kodu: {report['code_version']}",
            ],
        }
        if report["source"] == "demo":
            doc["summary"].append(
                "Dane demonstracyjne. Ten dokument przedstawia działanie systemu "
                "na danych syntetycznych; nie opisuje wyników rzeczywistego konta."
            )
        if totals["spend"] is not None and Decimal(totals["spend"]) == 0:
            doc["summary"].append(
                "W wybranym okresie nie odnotowano wydatków. Brak emisji nie "
                "pozwala ocenić skuteczności ani sam w sobie stwierdzić awarii konta."
            )
        if doc["coverage"] == "partial":
            doc["summary"].append(
                "Audyt częściowy. Wnioski dotyczą wyłącznie dostępnych danych; "
                "niesprawdzone obszary wskazano w zakresie audytu."
            )
        if weekly:
            _weekly_sections(report, doc, currency)
        else:
            _account_sections(report, doc, currency)
        if report.get("recommendations"):
            recommendations = [
                {
                    "title": "Rekomendacje",
                    "new_page": not weekly,
                    "paragraphs": [
                        "Poniższe działania są propozycjami. "
                        "Eksport raportu nie wykonuje zmian w kampaniach."
                    ],
                }
            ]
            for index, item in enumerate(report["recommendations"], 1):
                priority = {"high": "Wysoki", "medium": "Średni", "low": "Niski"}.get(
                    item.get("priority"), "Nieokreślony"
                )
                paragraphs = [
                    item["observation"],
                    "Proponowane działanie: " + item["suggested_action"],
                ]
                if item.get("campaign_id"):
                    paragraphs.append("Kampania: " + item["campaign_id"])
                if item.get("evidence"):
                    facts = "; ".join(
                        f"{LABELS.get(key, key)}: {data}" for key, data in item["evidence"].items()
                    )
                    paragraphs.append("Dowody: " + facts)
                recommendations.append(
                    {"title": f"{index:02d} / Priorytet: {priority}", "paragraphs": paragraphs}
                )
            doc["sections"][1:1] = recommendations
        return PdfDocument.model_validate_json(json.dumps(doc))
    except (KeyError, TypeError, IndexError, InvalidOperation):
        raise AppError("PDF_INPUT", "Raport nie zawiera wymaganych danych eksportu.", 2) from None


def _account_sections(report, doc, currency):
    campaigns = report["campaigns"]
    if report["campaign_count"] != len(campaigns):
        raise AppError("PDF_INPUT", "Lista kampanii w raporcie jest niepełna.", 2)
    doc["summary"].append(
        f"Raport obejmuje {len(campaigns)} kampanii dostępnych w zapisanych danych."
    )
    rows = [
        [LABELS.get(key, key), metric_value(metric)]
        for key, metric in report["summary"]["metrics"].items()
    ]
    doc["sections"].append(table("Wskaźniki emisji", ["Wskaźnik", "Wartość"], rows, [3, 2], [1]))
    if report.get("coverage"):
        rows = [
            [
                LABELS.get(item["area"], item["area"]),
                STATUSES.get(item["status"], item["status"]),
                item["detail"],
            ]
            for item in report["coverage"]
        ]
        doc["sections"].append(
            table("Zakres audytu", ["Obszar", "Ocena", "Zakres sprawdzenia"], rows, [1.2, 1, 3])
        )
    for group in report["goal_groups"]:
        rows = [
            [LABELS.get(key, key), metric_value(metric)] for key, metric in group["metrics"].items()
        ]
        rows.insert(0, ["Liczba wyników", value(group["totals"]["conversions"])])
        rows.insert(0, ["Wydatki", value(group["totals"]["spend"], currency)])
        doc["sections"].append(
            table(
                f"Cel: {group['goal_id']} / {GOALS.get(group['goal_type'], group['goal_type'])}",
                ["Wskaźnik", "Wartość"],
                rows,
                [3, 2],
                [1],
            )
        )
    rows = [
        [
            f"{row['name']}\nID: {row['campaign_id']}\n"
            f"Cel Meta: {row.get('objective') or 'brak danych'}",
            row["status_at_snapshot"],
            value(row["totals"]["spend"], currency),
            value(row["totals"]["impressions"]),
            value(row["totals"]["link_clicks"]),
        ]
        for row in campaigns
    ]
    section = table(
        "Wszystkie kampanie",
        ["Kampania", "Status", f"Wydatki ({currency})", "Wyświetlenia", "Kliknięcia linku"],
        rows,
        [3.5, 1.2, 1.3, 1.7, 1.35],
        [2, 3, 4],
    )
    section["paragraphs"] = [
        "Status kampanii dotyczy chwili pobrania. Nie jest potwierdzeniem emisji "
        "zestawów ani reklam w całym okresie."
    ]
    section["new_page"] = True
    doc["sections"].append(section)
    # Preserve mapped outcomes and every reported action type, without summing aliases.
    outcome_rows, actions = [], []
    for row in campaigns:
        if row.get("measurement_status") == "mapped":
            selected = [
                f"{LABELS.get(k, k)}: {metric_value(v)}"
                for k, v in row["metrics"].items()
                if k in ("cpl", "cpa", "roas", "cpql")
            ]
            outcome_rows.append(
                [
                    f"{row['name']}\n{row['campaign_id']}",
                    row["goal_id"],
                    value(row["totals"]["conversions"]),
                    "\n".join(selected),
                ]
            )
        for key in sorted(
            set(row.get("reported_actions", {})) | set(row.get("reported_action_values", {}))
        ):
            actions.append(
                [
                    f"{row['name']}\n{row['campaign_id']}",
                    key,
                    value(row.get("reported_actions", {}).get(key)),
                    value(row.get("reported_action_values", {}).get(key), currency),
                ]
            )
    if outcome_rows:
        doc["sections"].append(
            table(
                "Wyniki według celu kampanii",
                ["Kampania", "Cel", "Wyniki", "Koszt / zwrot"],
                outcome_rows,
                [3, 1.4, 1, 1.8],
                [2],
            )
        )
    if actions:
        section = table(
            "Zdarzenia raportowane przez Meta",
            ["Kampania", "Typ zdarzenia", "Liczba", f"Wartość ({currency})"],
            actions,
            [2.8, 2.8, 1, 1.4],
            [2, 3],
        )
        section["paragraphs"] = [
            "Typy zdarzeń mogą się nakładać. Ich sumowanie nie daje liczby "
            "unikalnych leadów ani zakupów. Wartość i liczba są osobnymi polami."
        ]
        doc["sections"].append(section)


def _weekly_sections(report, doc, currency):
    previous = report["periods"]["previous"]
    doc["summary"].append(
        f"Porównanie z okresem {previous['since']} - {previous['until']}. Cel: {report['goal_id']}."
    )
    comparison = report["summary"]
    rows = [
        [
            LABELS[key],
            value(comparison["previous"]["totals"][key], currency if key == "spend" else None),
            value(comparison["current"]["totals"][key], currency if key == "spend" else None),
        ]
        for key in ("spend", "impressions", "link_clicks", "conversions")
    ]
    doc["sections"].append(
        table(
            "Wolumen wyników",
            ["Wskaźnik", "Poprzedni okres", "Bieżący okres"],
            rows,
            [2, 1.5, 1.5],
            [1, 2],
        )
    )
    rows = []
    for key, current in comparison["current"]["metrics"].items():
        rows.append(
            [
                LABELS.get(key, key),
                metric_value(comparison["previous"]["metrics"][key]),
                metric_value(current),
                metric_value(comparison["relative_changes"][key]),
            ]
        )
    doc["sections"].append(
        table(
            "Porównanie okresów",
            ["Wskaźnik", "Poprzedni okres", "Bieżący okres", "Zmiana względna"],
            rows,
            [2, 1.6, 1.6, 1.5],
            [1, 2, 3],
        )
    )
    checks = [
        [
            LABELS.get(key, key),
            value(item["target"], currency if key in ("cpl", "cpa", "cpql") else "x"),
            value(item["observed"], currency if key in ("cpl", "cpa", "cpql") else "x"),
            {"met": "Spełniony", "not_met": "Niespełniony", "unavailable": "Brak danych"}[
                item["status"]
            ],
        ]
        for key, item in report["target_checks"].items()
    ]
    doc["sections"].append(
        table("Ocena celów", ["Wskaźnik", "Cel", "Wynik", "Ocena"], checks, [2, 1, 1, 2], [1, 2])
    )
    for row in report["campaigns"]:
        rows = [
            [
                "Wydatki",
                value(row["previous"]["totals"]["spend"], currency),
                value(row["current"]["totals"]["spend"], currency),
            ],
            [
                "Wyniki",
                value(row["previous"]["totals"]["conversions"]),
                value(row["current"]["totals"]["conversions"]),
            ],
        ]
        rows += [
            [
                LABELS.get(key, key),
                metric_value(row["previous"]["metrics"][key]),
                metric_value(metric),
            ]
            for key, metric in row["current"]["metrics"].items()
        ]
        for key in ("impressions", "link_clicks"):
            rows.append(
                [
                    LABELS[key],
                    value(row["previous"]["totals"][key]),
                    value(row["current"]["totals"][key]),
                ]
            )
        section = table(
            f"Kampania {row['campaign_id']}",
            ["Wskaźnik", "Poprzedni okres", "Bieżący okres"],
            rows,
            [2, 1.5, 1.5],
            [1, 2],
        )
        section["paragraphs"] = [row["name"]]
        doc["sections"].append(section)


def prepare(input_path: Path, client: str, account: str, notes_path: Path | None = None):
    raw = load_json(input_path)
    if raw.get("client_id") != client or raw.get("account_id") != account:
        raise AppError(
            "SCOPE_MISMATCH", "Plik raportu nie należy do wskazanego klienta i konta.", 3
        )
    doc = document_from_report(raw)
    if notes_path:
        notes = PdfNotes.model_validate_json(json.dumps(load_json(notes_path)))
        if (notes.client_id, notes.account_id, notes.report_id, notes.snapshot_id) != (
            client,
            account,
            raw.get("run_id"),
            raw.get("snapshot_id"),
        ):
            raise AppError("SCOPE_MISMATCH", "Komentarz dotyczy innego raportu lub snapshotu.", 3)
        from meta_ads_manager.pdf_models import PdfSection

        doc.sections.insert(
            0,
            PdfSection(
                title="Komentarz analityczny",
                paragraphs=[
                    "Interpretacja dołączona do danych raportu. Rekomendacje nie oznaczają "
                    "wykonania zmian w kampaniach."
                ],
                new_page=False,
            ),
        )
        doc.sections[1:1] = notes.sections
        # Internal rule provenance remains in the source notes, outside report prose.
    return doc
