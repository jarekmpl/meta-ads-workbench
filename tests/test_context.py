import argparse
import io
import json
import zipfile
from datetime import date

import pytest
from pydantic import ValidationError
from reportlab.pdfgen import canvas

from meta_ads_manager.context_documents import extract
from meta_ads_manager.context_engine import (
    add_rule,
    compare_documents,
    document,
    make_basis,
    meeting_pair,
    rule_status,
    rules_view,
    search,
    verify_basis,
    verify_reference,
)
from meta_ads_manager.context_models import ContextReference, ContextRule
from meta_ads_manager.errors import AppError
from meta_ads_manager.workspace import add_context, run, set_context_status

TODAY = date(2026, 9, 10)


@pytest.fixture
def client(tmp_path, monkeypatch):
    root = tmp_path / "client-a"
    root.mkdir()
    (root / "workspace.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "kind": "operator_workspace",
                "client_id": "client-a",
                "name": "Client A",
            }
        )
    )
    monkeypatch.chdir(root)
    return root


def add(root, text="Mówimy na Ty. Rabat wynosi 10%.", **kw):
    source = root / "source.md"
    source.write_text(text)
    args = dict(
        file=source,
        title="Ustalenia",
        type="meeting",
        project="jesien",
        tag=[],
        valid_until=None,
        document_date="2026-09-01",
    )
    args.update(kw)
    item = add_context(root, argparse.Namespace(**args))
    set_context_status(
        root,
        argparse.Namespace(
            id=item["id"], status="confirmed", reason="Operator potwierdził notatkę."
        ),
    )
    return item


def rule(root, item, identifier="rabat-1", value="10%", **kw):
    data = dict(
        schema_version="1.0",
        kind="context_rule",
        client_id="client-a",
        rule_id=identifier,
        key="offer.discount",
        value=value,
        project="jesien",
        sources=[document(root, item["id"])["chunks"][0]],
    )
    data.update(kw)
    return ContextRule.model_validate_json(json.dumps(data))


def confirm(root, definition):
    add_rule(root, definition)
    return rule_status(
        root,
        definition.rule_id,
        "confirmed",
        1,
        "Operator",
        "Potwierdzam treść i zakres ustalenia.",
    )


def test_search_polish_scope_and_dates(client):
    item = add(client, valid_until="2026-09-30")
    add(client, "Rabat innej promocji", project="zima")
    add(client, "Rabat historyczny", valid_until="2026-08-30")
    add(client, "Rabat przyszły", valid_from="2026-10-01")
    general = add(client, "Zawsze mówimy na Ty.", project=None)
    result = search(client, "mowimy", "jesien", TODAY)
    assert {x["reference"]["material_id"] for x in result["hits"]} == {item["id"], general["id"]}
    assert len(search(client, "rabat", "jesien", TODAY)["hits"]) == 1
    assert len(search(client, "rabat", "jesien", TODAY, history=True)["hits"]) == 3
    assert not search(client, "rabat", None, TODAY)["hits"]
    assert search(client, "nieznaneslowo", "jesien", TODAY)["total_hits"] == 0


def test_pdf_pages_and_blank_coverage():
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream)
    pdf.drawString(30, 700, "Discount 10%")
    pdf.showPage()
    pdf.showPage()
    pdf.save()
    doc = extract(stream.getvalue(), ".pdf", "a", {"id": "doc", "sha256": "a" * 64, "title": "PDF"})
    assert doc["chunks"][0]["locator"].startswith("page:1/")
    assert doc["chunks"][0]["quote"] == "Discount 10%"
    assert "page:2" in doc["warnings"][0]


def make_docx(xml):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return data.getvalue()


def test_docx_paragraph_table_deleted_text_and_no_external_reads():
    raw = make_docx("""<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body><w:p><w:r><w:t>Komunikacja na Ty.</w:t></w:r>
    <w:del><w:r><w:t>Usunięte</w:t></w:r></w:del></w:p>
    <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Rabat</w:t></w:r></w:p></w:tc>
    <w:tc><w:p><w:r><w:t>10%</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
    </w:body></w:document>""")
    doc = extract(raw, ".docx", "a", {"id": "doc", "sha256": "a" * 64, "title": "Word"})
    assert doc["chunks"][0]["quote"] == "Komunikacja na Ty."
    assert doc["chunks"][1]["quote"] == "Rabat | 10%"
    assert doc["chunks"][1]["locator"].startswith("table:1/row:1")
    assert any(w.startswith("tracked_changes") for w in doc["warnings"])


@pytest.mark.parametrize(
    "payload,suffix,code",
    [
        (b"bad", ".pdf", "CONTEXT_FORMAT"),
        (b"bad", ".docx", "CONTEXT_FORMAT"),
        (b"bad", ".doc", "CONTEXT_UNSUPPORTED"),
        (b"\xff", ".txt", "CONTEXT_FORMAT"),
        (make_docx("<!DOCTYPE x><x/>"), ".docx", "CONTEXT_FORMAT"),
    ],
)
def test_unreadable_is_not_empty_evidence(payload, suffix, code):
    with pytest.raises(AppError) as error:
        extract(payload, suffix, "a", {"id": "doc", "sha256": "a" * 64, "title": "File"})
    assert error.value.code == code


def test_encrypted_and_empty_pdf():
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    data = io.BytesIO()
    writer.write(data)
    doc = extract(data.getvalue(), ".pdf", "a", {"id": "doc", "sha256": "a" * 64, "title": "x"})
    assert doc["status"] == "no_text" and not doc["chunks"]
    writer.encrypt("secret")
    data = io.BytesIO()
    writer.write(data)
    with pytest.raises(AppError) as error:
        extract(data.getvalue(), ".pdf", "a", {})
    assert error.value.code == "CONTEXT_ENCRYPTED"


def test_changed_file_foreign_client_and_forged_quote(client):
    item = add(client)
    ref = document(client, item["id"])["chunks"][0]
    assert verify_reference(client, ref)["status"] == "ok"
    for values in (
        {"quote": "Rabat 90%"},
        {"client_id": "other"},
        {"locator": "page:999"},
        {"sha256": "0" * 64},
        {"title": "Sfałszowana nazwa"},
    ):
        with pytest.raises(AppError):
            verify_reference(client, {**ref, **values})
    (client / item["file"]).write_text("Podmieniony plik")
    with pytest.raises(AppError):
        verify_reference(client, ref)
    result = search(client, "rabat", "jesien", TODAY)
    assert not result["hits"] and result["coverage"][0]["status"] == "CONTEXT_CHANGED"


def test_confirmed_rules_conflict_and_explicit_resolution(client):
    first = add(client)
    second = add(client, "Rabat wynosi 20%.", document_date="2026-09-08", version_of=first["id"])
    confirm(client, rule(client, first))
    confirm(client, rule(client, second, "rabat-2", "20%"))
    view = rules_view(client, "jesien", TODAY)
    assert len(view["conflicts"]) == 1 and not view["applicable"]
    with pytest.raises(AppError):
        make_basis(client, ["rabat-2"], "jesien", TODAY, "Oferta do reklamy")
    retired = rule_status(
        client, "rabat-1", "retired", 2, "Operator", "Potwierdzony rabat 20% zastępuje 10%."
    )
    assert len(retired["history"]) == 2
    assert [
        r["definition"]["rule_id"] for r in rules_view(client, "jesien", TODAY)["applicable"]
    ] == ["rabat-2"]
    basis = make_basis(client, ["rabat-2"], "jesien", TODAY, "Oferta do reklamy")
    verify_basis(client, basis, "client-a", "jesien")
    with pytest.raises(AppError):
        verify_basis(client, basis, "client-a", "zima")
    with pytest.raises(AppError):
        rule_status(client, "rabat-1", "confirmed", 3, "Agent", "Nowszy plik")


def test_scope_dates_draft_and_stale_material_block_basis(client):
    item = add(client, valid_from="2026-09-01", valid_until="2026-09-30")
    definition = rule(client, item)
    add_rule(client, definition)
    with pytest.raises(AppError):
        make_basis(client, ["rabat-1"], "jesien", TODAY, "Oferta")
    rule_status(client, "rabat-1", "confirmed", 1, "Operator", "Potwierdzam")
    assert not rules_view(client, "zima", TODAY)["applicable"]
    assert not rules_view(client, "jesien", date(2026, 10, 1))["applicable"]
    assert not rules_view(client, "jesien", date(2026, 8, 1))["applicable"]
    with pytest.raises(AppError):
        add_rule(client, rule(client, item, "foreign-project", project=None))
    with pytest.raises(AppError):
        add_rule(client, rule(client, item, "disjoint", valid_from="2026-10-01"))
    set_context_status(
        client, argparse.Namespace(id=item["id"], status="superseded", reason="Nowa")
    )
    assert not rules_view(client, "jesien", TODAY)["applicable"]


def test_global_rule_conflicts_with_promotion_but_not_other_promotions(client):
    global_doc = add(client, project=None)
    local_doc = add(client, "Rabat 20%")
    confirm(client, rule(client, global_doc, "global", project=None))
    confirm(client, rule(client, local_doc, "local", "20%"))
    assert rules_view(client, "jesien", TODAY)["conflicts"]
    assert not rules_view(client, "zima", TODAY)["conflicts"]
    assert len(rules_view(client, None, TODAY)["applicable"]) == 1


def test_rule_immutable_and_stale_revision(client):
    item = add(client)
    definition = rule(client, item)
    assert add_rule(client, definition) == add_rule(client, definition)
    with pytest.raises(AppError):
        add_rule(client, rule(client, item, value="90%"))
    with pytest.raises(AppError):
        rule_status(client, "rabat-1", "confirmed", 9, "Operator", "Tak")
    with pytest.raises(ValidationError):
        ContextReference.model_validate({"invalid": True})


def test_compare_latest_meetings_uses_event_date_not_import_order(client):
    newer = add(client, "Rabat 20%.\nTermin bez zmian.", document_date="2026-09-08")
    older = add(client, "Rabat 10%.\nTermin bez zmian.", document_date="2026-09-01")
    assert meeting_pair(client, "jesien") == (older["id"], newer["id"])
    comparison = compare_documents(client, *meeting_pair(client, "jesien"))
    assert len(comparison["changes"]) == 1
    assert comparison["changes"][0]["before"][0]["quote"] == "Rabat 10%."
    assert comparison["changes"][0]["after"][0]["quote"] == "Rabat 20%."
    assert comparison["rules_changed"] is False
    add(client, document_date="2026-09-08")
    with pytest.raises(AppError):
        meeting_pair(client, "jesien")


def test_cli_extraction_basis_and_path_protection(client, capsys):
    item = add(client)
    assert run(["context", "read", "--id", item["id"], "--output", "output/read.json"]) == 0
    doc = json.loads((client / "output/read.json").read_text())
    assert doc["chunks"][0]["quote"].startswith("Mówimy")
    capsys.readouterr()
    path = client / "output/rule.json"
    path.write_text(rule(client, item).model_dump_json())
    assert run(["context", "rule-add", "--file", str(path)]) == 0
    assert (
        run(
            [
                "context",
                "rule-status",
                "--id",
                "rabat-1",
                "--status",
                "confirmed",
                "--expected-revision",
                "1",
                "--actor",
                "Operator",
                "--reason",
                "Tak",
            ]
        )
        == 0
    )
    assert (
        run(
            [
                "context",
                "basis",
                "--project",
                "jesien",
                "--as-of",
                "2026-09-10",
                "--rule",
                "rabat-1",
                "--used-for",
                "Oferta",
                "--output",
                "output/basis.json",
            ]
        )
        == 0
    )
    assert json.loads((client / "output/basis.json").read_text())["rule_ids"] == ["rabat-1"]
    for output in ("context/rules.json", "../foreign.json", "output/read.json"):
        assert run(["context", "read", "--id", item["id"], "--output", output]) != 0
    assert run(["context", "rule-add", "--file", "../foreign.json"]) != 0


def test_symlinked_material_and_foreign_rules_index(client, tmp_path):
    item = add(client)
    path = client / item["file"]
    path.unlink()
    path.symlink_to(tmp_path / "foreign.md")
    with pytest.raises(AppError):
        document(client, item["id"])
    (client / "context/rules.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "client_id": "other",
                "items": [],
            }
        )
    )
    with pytest.raises(AppError):
        rules_view(client, "jesien", TODAY)


def test_recommendation_captures_basis_and_replay_preserves_history(client):
    from test_decisions import goal, recommendation

    from meta_ads_manager.decision_store import Decisions

    item = add(client)
    confirm(client, rule(client, item))
    basis = make_basis(client, ["rabat-1"], "jesien", TODAY, "Rabat w treści reklamy")
    rec = recommendation(context_basis=basis.model_dump(mode="json"))
    with Decisions(client / "data/decisions.sqlite3", "client-a", "act_123") as registry:
        registry.save_goal(goal(project_id="jesien"))
        row = registry.add_recommendation(rec)
        saved = row["data"]["definition"]["context_basis"]
        assert saved["sources"][0]["sha256"] == item["sha256"]
        assert saved["used_for"] == "Rabat w treści reklamy"
        forged = basis.model_copy(deep=True)
        forged.sources[0].quote = "Rabat 80%"
        with pytest.raises(AppError):
            registry.add_recommendation(
                recommendation(
                    recommendation_id="forged",
                    action="Inne działanie",
                    context_basis=forged.model_dump(mode="json"),
                )
            )
        rule_status(client, "rabat-1", "retired", 2, "Operator", "Zmiana oferty")
        assert registry.get("recommendation", "rec-1") == row
        assert registry.add_recommendation(rec)["data"] == row["data"]
        with pytest.raises(AppError):
            registry.add_recommendation(
                recommendation(
                    recommendation_id="new",
                    action="Nowe działanie",
                    context_basis=basis.model_dump(mode="json"),
                )
            )
        assert len(registry.recommendations()) == 1


def test_legacy_recommendation_without_context_field_replays(client):
    from test_decisions import goal, recommendation

    from meta_ads_manager.decision_store import Decisions, canonical

    with Decisions(client / "data/decisions.sqlite3", "client-a", "act_123") as registry:
        registry.save_goal(goal())
        row = registry.add_recommendation(recommendation())
        del row["data"]["definition"]["context_basis"]
        with registry.db:
            registry.db.execute(
                "UPDATE records SET payload=? WHERE category='recommendation'",
                (canonical(row["data"]),),
            )
        assert registry.add_recommendation(recommendation())["id"] == "rec-1"


def test_docx_size_guard_and_text_limit(monkeypatch):
    import meta_ads_manager.context_documents as reader

    monkeypatch.setattr(reader, "MAX_XML", 5)
    with pytest.raises(AppError) as error:
        extract(make_docx("<document/>"), ".docx", "a", {})
    assert error.value.code == "CONTEXT_LIMIT"
    monkeypatch.setattr(reader, "MAX_TEXT", 5)
    with pytest.raises(AppError) as error:
        extract(b"123456", ".txt", "a", {})
    assert error.value.code == "CONTEXT_LIMIT"


def test_mismatched_dates_and_missing_meeting_dates(client):
    with pytest.raises(AppError):
        add(client, valid_from="2026-11-01", valid_until="2026-10-01")
    add(client)
    add(client, document_date=None)
    with pytest.raises(AppError):
        meeting_pair(client, "jesien")


def test_new_draft_flags_possible_conflict_without_replacing_confirmed_rule(client):
    old = add(client)
    new = add(client, "Rabat wynosi 20%.")
    confirm(client, rule(client, old))
    add_rule(client, rule(client, new, "rabat-2", "20%"))
    view = rules_view(client, "jesien", TODAY)
    assert not view["conflicts"] and len(view["potential_conflicts"]) == 1
    assert view["applicable"][0]["definition"]["rule_id"] == "rabat-1"


def test_identical_files_keep_distinct_material_references(client):
    a, b = add(client), add(client)
    confirm(client, rule(client, a))
    confirm(client, rule(client, b, "rabat-2"))
    basis = make_basis(client, ["rabat-1", "rabat-2"], "jesien", TODAY, "Oferta")
    assert len(basis.sources) == 2
    assert {r.material_id for r in basis.sources} == {a["id"], b["id"]}


def test_unconfirmed_material_and_tracked_word_cannot_confirm_rule(client):
    item = add(client)
    add_rule(client, rule(client, item))
    set_context_status(client, argparse.Namespace(id=item["id"], status="draft", reason="Do oceny"))
    with pytest.raises(AppError) as error:
        rule_status(client, "rabat-1", "confirmed", 1, "Operator", "Tak")
    assert error.value.code == "CONTEXT_UNCONFIRMED"
    path = client / "tracked.docx"
    path.write_bytes(
        make_docx("""<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
        <w:body><w:p><w:ins><w:r><w:t>Rabat 20%</w:t></w:r></w:ins></w:p></w:body>
        </w:document>""")
    )
    item = add_context(
        client,
        argparse.Namespace(
            file=path, title="Roboczy", type="note", project="jesien", tag=[], valid_until=None
        ),
    )
    set_context_status(client, argparse.Namespace(id=item["id"], status="confirmed", reason="Tak"))
    add_rule(client, rule(client, item, "tracked"))
    with pytest.raises(AppError) as error:
        rule_status(client, "tracked", "confirmed", 1, "Operator", "Tak")
    assert error.value.code == "CONTEXT_REVISIONS"
