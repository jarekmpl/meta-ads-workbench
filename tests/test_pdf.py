import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from meta_ads_manager.analytics import weekly_review
from meta_ads_manager.cli import run
from meta_ads_manager.errors import AppError
from meta_ads_manager.pdf_content import document_from_report, prepare
from meta_ads_manager.pdf_models import PdfDocument, PdfNotes
from meta_ads_manager.provider import DemoProvider
from meta_ads_manager.reporting import account_audit, account_report

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def report():
    provider = DemoProvider()
    return account_report(
        "sync_pdf_test",
        provider.available("demo-shop", "act_DEMO_SHOP"),
        provider.client("demo-shop"),
        date(2026, 8, 10),
        date(2026, 9, 8),
    )


def save(tmp_path, data, name="input.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data, ensure_ascii=False))
    return path


@pytest.mark.parametrize(
    "kind,model,example",
    [("pdf_document", PdfDocument, "analysis"), ("pdf_notes", PdfNotes, "notes")],
)
def test_pdf_contracts_and_examples(kind, model, example):
    model.model_validate_json((ROOT / "examples/pdf" / f"{example}.json").read_text())
    assert json.loads((ROOT / "schemas" / f"{kind}.schema.json").read_text()) == (
        model.model_json_schema()
    )


def test_native_content_preserves_campaigns_outcomes_and_audit_limits(report):
    doc = document_from_report(account_audit(report))
    assert doc.source == "demo" and doc.coverage == "partial"
    text = doc.model_dump_json()
    assert all(row["campaign_id"] in text for row in report["campaigns"])
    assert "4,50 x" in text and "5 080,00 PLN" in text
    assert "brak danych" in text
    titles = [section.title for section in doc.sections]
    assert titles.index("Rekomendacje") < titles.index("Wszystkie kampanie")
    assert doc.limitations == account_audit(report)["limitations"]


def test_weekly_keeps_both_periods_and_all_campaigns():
    provider = DemoProvider()
    report = weekly_review(
        "sync_pdf_weekly",
        provider.available("demo-shop", "act_DEMO_SHOP"),
        provider.goal("demo-shop", "act_DEMO_SHOP", "commerce-pl"),
    )
    report["campaigns"][0]["name"] = "Bardzo długa nazwa " * 60
    doc = document_from_report(report)
    text = doc.model_dump_json()
    assert report["periods"]["previous"]["since"] in text
    assert all(row["campaign_id"] in text for row in report["campaigns"])
    assert "Bardzo długa nazwa " * 60 in text
    assert "4,50 x" in text and "40,00 PLN" in text


def test_export_rejects_wrong_scope_failed_report_and_missing_campaigns(tmp_path, report):
    with pytest.raises(AppError, match="klienta"):
        prepare(save(tmp_path, report), "other", report["account_id"])
    with pytest.raises(AppError, match="nieudanego"):
        prepare(save(tmp_path, {"ok": False}), "other", "account")
    report["campaigns"].pop()
    with pytest.raises(AppError, match="niepełna"):
        document_from_report(report)


def test_notes_require_exact_report_and_snapshot(tmp_path, report):
    notes = {
        "kind": "pdf_notes",
        "client_id": report["client_id"],
        "account_id": report["account_id"],
        "report_id": report["run_id"],
        "snapshot_id": "sync_foreign",
        "knowledge_version": "test-1",
        "rule_ids": ["RULE-TEST"],
        "sections": [{"title": "Komentarz specjalisty", "paragraphs": ["To hipoteza."]}],
    }
    source = save(tmp_path, report)
    with pytest.raises(AppError, match="snapshotu"):
        prepare(
            source, report["client_id"], report["account_id"], save(tmp_path, notes, "notes.json")
        )
    notes["snapshot_id"] = report["snapshot_id"]
    doc = prepare(
        source, report["client_id"], report["account_id"], save(tmp_path, notes, "notes.json")
    )
    assert doc.sections[1].title == "Komentarz specjalisty"
    rendered_content = doc.model_dump_json()
    assert "test-1" not in rendered_content and "RULE-TEST" not in rendered_content
    saved_notes = json.loads((tmp_path / "notes.json").read_text())
    assert saved_notes["knowledge_version"] == "test-1"
    assert saved_notes["rule_ids"] == ["RULE-TEST"]
    assert json.loads(source.read_text()) == report


def test_pdf_export_cli_branding_provenance_and_no_overwrite(tmp_path, report, capsys):
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")
    source = save(tmp_path, {"ok": True, "data": account_audit(report)})
    output = tmp_path / "audit.pdf"
    args = [
        "pdf",
        "export",
        "--client",
        report["client_id"],
        "--account",
        report["account_id"],
        "--input",
        str(source),
        "--pdf",
        str(output),
    ]
    assert run(args) == 0
    result = json.loads(capsys.readouterr().out)["data"]
    reader = pypdf.PdfReader(output)
    assert result["page_count"] == len(reader.pages) >= 2
    for index, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        assert "DANE DEMONSTRACYJNE" in text and "AUDYT CZĘŚCIOWY" in text
        assert f"{index} / {len(reader.pages)}" in text
        assert len(page.images) == 1
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Wyświetlenia" in text and "5 080,00 PLN" in text
    assert all(row["campaign_id"] in text for row in report["campaigns"])
    assert result["input_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    original = output.read_bytes()
    assert result["pdf_sha256"] == hashlib.sha256(original).hexdigest()
    assert result["visual_review"] == "required"
    assert run(args) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "OUTPUT_EXISTS"
    assert output.read_bytes() == original


def test_long_table_repeats_headers_and_escapes_markup(tmp_path):
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")
    pytest.importorskip("pypdfium2")
    from meta_ads_manager.pdf_export import export_pdf, render_pdf

    raw = json.loads((ROOT / "examples/pdf/analysis.json").read_text())
    raw["sections"] = [
        {
            "title": "Duża tabela",
            "table": {
                "columns": ["Identyfikator", "Treść"],
                "widths": [1, 3],
                "rows": [
                    [f"wiersz_{index:03d}", 'Zażółć gęślą jaźń <img src="/missing.png"/>']
                    for index in range(100)
                ],
            },
        }
    ]
    source = save(tmp_path, raw)
    output = tmp_path / "long.pdf"
    export_pdf(source, output, raw["client_id"], raw["account_id"])
    pages = pypdf.PdfReader(output).pages
    assert len(pages) >= 3
    text = "\n".join(page.extract_text() for page in pages)
    assert all(f"wiersz_{index:03d}" in text for index in range(100))
    assert '<img src="/missing.png"/>' in text and "Zażółć gęślą jaźń" in text
    for page in pages:
        if "wiersz_" in page.extract_text():
            assert "Identyfikator" in page.extract_text()
    previews = render_pdf(output, tmp_path / "preview", dpi=72)
    assert previews["page_count"] == len(pages)
    assert all(Path(path).stat().st_size > 1000 for path in previews["pages"])
