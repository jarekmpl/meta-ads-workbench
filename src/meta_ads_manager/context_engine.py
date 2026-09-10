"""Client-local retrieval, grounded rules, conflicts and frozen recommendation evidence."""

import hashlib
import json
import re
import unicodedata
from datetime import UTC, date, datetime
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
from uuid import uuid4

from meta_ads_manager.context_documents import extract
from meta_ads_manager.context_models import ContextBasis, ContextReference, ContextRule
from meta_ads_manager.errors import AppError
from meta_ads_manager.meta_connection import save_private
from meta_ads_manager.workspace import confined, context_index, context_lock, workspace_info


def fail(code, message):
    raise AppError(code, message, 2)


def stamp():
    return datetime.now(UTC).isoformat()


def material(root, identifier):
    item = next((x for x in context_index(root)["items"] if x["id"] == identifier), None)
    if item is None:
        fail("CONTEXT_NOT_FOUND", "Brak materiału w przestrzeni tego klienta.")
    return item


def document(root, identifier):
    item = material(root, identifier)
    path = confined(root, Path(item["file"]))
    if not path.is_file() or path.stat().st_size > 50 * 1024 * 1024:
        fail("CONTEXT_CHANGED", "Brak oryginalnego materiału lub przekroczony limit pliku.")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != item["sha256"]:
        fail("CONTEXT_CHANGED", "Materiał zmienił się; zaimportuj osobną wersję.")
    return {
        "material": item,
        **extract(payload, path.suffix, workspace_info(root)["client_id"], item),
    }


def in_date(item, on):
    return (not item.get("valid_from") or item["valid_from"] <= str(on)) and (
        not item.get("valid_until") or item["valid_until"] >= str(on)
    )


def in_project(item, project):
    # No project selected means general client rules, never a mix of promotions.
    return item.get("project") is None or item["project"] == project


def normalized(text):
    text = text.lower().replace("ł", "l")
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def tokens(text):
    return set(re.findall(r"[a-z0-9]+", normalized(text)))


def search(root, query, project=None, on=None, limit=10, history=False):
    on = on or date.today()
    terms = tokens(query)
    if not terms or not 1 <= limit <= 50:
        fail("CONTEXT_QUERY", "Podaj słowa do wyszukania i limit od 1 do 50.")
    hits, coverage = [], []
    for item in context_index(root)["items"]:
        if not in_project(item, project):
            continue
        if not history and (item["status"] == "superseded" or not in_date(item, on)):
            continue
        try:
            doc = document(root, item["id"])
        except AppError as exc:
            coverage.append({"material_id": item["id"], "status": exc.code})
            continue
        coverage.append(
            {"material_id": item["id"], "status": doc["status"], "warnings": doc["warnings"]}
        )
        for ref in doc["chunks"]:
            words = tokens(ref["quote"])
            matched = terms & words
            if not matched:
                continue
            score = len(matched) / len(terms)
            if normalized(query) in normalized(ref["quote"]):
                score += 1
            hits.append(
                {
                    "score": round(score, 4),
                    "reference": ref,
                    "material_status": item["status"],
                    "applicable_date": in_date(item, on),
                }
            )
    hits.sort(
        key=lambda hit: (
            -hit["score"],
            hit["reference"]["material_id"],
            hit["reference"]["locator"],
        )
    )
    return {
        "client_id": workspace_info(root)["client_id"],
        "project": project,
        "as_of": str(on),
        "method": "lexical",
        "total_hits": len(hits),
        "hits": hits[:limit],
        "coverage": coverage,
    }


def verify_reference(root, ref, cache=None):
    if isinstance(ref, dict):
        ref = ContextReference.model_validate(ref)
    if ref.client_id != workspace_info(root)["client_id"]:
        fail("SCOPE_MISMATCH", "Odwołanie dotyczy innego klienta.")
    cache = {} if cache is None else cache
    if ref.material_id not in cache:
        cache[ref.material_id] = document(root, ref.material_id)
    doc = cache[ref.material_id]
    if ref.model_dump() not in doc["chunks"]:
        fail("CONTEXT_REFERENCE", "Cytat, wersja lub lokalizacja nie zgadza się z dokumentem.")
    return doc


def rule_index(root):
    client = workspace_info(root)["client_id"]
    path = confined(root, Path("context/rules.json"))
    if not path.exists():
        return {"schema_version": "1.0", "client_id": client, "items": []}
    data = json.loads(path.read_text())
    if data.get("client_id") != client or data.get("schema_version") != "1.0":
        fail("SCOPE_MISMATCH", "Rejestr ustaleń należy do innego klienta.")
    for row in data["items"]:
        rule = ContextRule.model_validate_json(json.dumps(row["definition"]))
        if rule.client_id != client:
            fail("SCOPE_MISMATCH", "Ustalenie należy do innego klienta.")
    return data


def save_rules(root, index):
    target = confined(root, Path("context/rules.json"), output=True)
    temporary = target.parent / f".rules-{uuid4().hex}.json"
    save_private(temporary, index)
    temporary.replace(target)


def check_rule_sources(root, rule, cache=None):
    if rule.client_id != workspace_info(root)["client_id"]:
        fail("SCOPE_MISMATCH", "Ustalenie należy do innego klienta.")
    docs = []
    for ref in rule.sources:
        doc = verify_reference(root, ref, cache)
        if not in_project(doc["material"], rule.project):
            fail("SCOPE_MISMATCH", "Materiał nie dotyczy projektu tego ustalenia.")
        docs.append(doc)
    starts = [str(rule.valid_from)] if rule.valid_from else []
    ends = [str(rule.valid_until)] if rule.valid_until else []
    starts += [d["material"]["valid_from"] for d in docs if d["material"].get("valid_from")]
    ends += [d["material"]["valid_until"] for d in docs if d["material"].get("valid_until")]
    since, until = max(starts, default="0001-01-01"), min(ends, default="9999-12-31")
    if since > until:
        fail("CONTEXT_DATES", "Ustalenie i jego materiały nie mają wspólnego terminu ważności.")
    return docs, since, until


def add_rule(root, rule):
    with context_lock(root):
        check_rule_sources(root, rule)
        index = rule_index(root)
        definition = rule.model_dump(mode="json")
        previous = next(
            (r for r in index["items"] if r["definition"]["rule_id"] == rule.rule_id), None
        )
        if previous:
            if previous["definition"] == definition:
                return previous
            fail("CONTEXT_IMMUTABLE", "Zmienione ustalenie zapisz pod nowym ID.")
        row = {
            "definition": definition,
            "status": "draft",
            "revision": 1,
            "created_at": stamp(),
            "history": [],
        }
        index["items"].append(row)
        save_rules(root, index)
        return row


def rule_status(root, identifier, status, expected, actor, reason):
    if status not in ("confirmed", "retired") or not actor.strip() or not reason.strip():
        fail("CONTEXT_DECISION", "Podaj decyzję operatora, autora i uzasadnienie.")
    with context_lock(root):
        index = rule_index(root)
        row = next((r for r in index["items"] if r["definition"]["rule_id"] == identifier), None)
        if row is None:
            fail("CONTEXT_NOT_FOUND", "Brak ustalenia.")
        if expected != row["revision"]:
            fail("REVISION_CONFLICT", "Ustalenie zmieniło status; odczytaj aktualną wersję.")
        if row["status"] == "retired" or row["status"] == status:
            fail("CONTEXT_DECISION", "Wycofane ustalenie zachowuje historię; dodaj nowe ID.")
        if status == "confirmed":
            rule = ContextRule.model_validate_json(json.dumps(row["definition"]))
            docs, _, _ = check_rule_sources(root, rule)
            if any(d["material"]["status"] != "confirmed" for d in docs):
                fail("CONTEXT_UNCONFIRMED", "Najpierw potwierdź materiały tego ustalenia.")
            if any(any(w.startswith("tracked_changes") for w in d["warnings"]) for d in docs):
                fail("CONTEXT_REVISIONS", "Zaimportuj uzgodnioną wersję bez śledzenia zmian.")
        row["history"].append(
            {
                "previous": row["status"],
                "status": status,
                "actor": actor,
                "reason": reason,
                "at": stamp(),
            }
        )
        row["status"] = status
        row["revision"] += 1
        save_rules(root, index)
        return row


def rules_view(root, project=None, on=None):
    on = on or date.today()
    rows, cache = [], {}
    for row in rule_index(root)["items"]:
        definition = row["definition"]
        if not in_project(definition, project):
            continue
        row = dict(row)
        row["blockers"] = []
        if row["status"] != "confirmed":
            row["blockers"].append(row["status"])
        try:
            rule = ContextRule.model_validate_json(json.dumps(definition))
            docs, since, until = check_rule_sources(root, rule, cache)
            row["effective_from"], row["effective_until"] = since, until
            if not since <= str(on) <= until:
                row["blockers"].append("outside_validity")
            if any(d["material"]["status"] != "confirmed" for d in docs):
                row["blockers"].append(
                    "source_superseded"
                    if any(d["material"]["status"] == "superseded" for d in docs)
                    else "source_not_confirmed"
                )
        except AppError as exc:
            row["blockers"].append(exc.code)
        rows.append(row)
    eligible = [row for row in rows if set(row["blockers"]) <= {"draft", "source_not_confirmed"}]
    conflicts, potential_conflicts = [], []
    for left, right in combinations(eligible, 2):
        a, b = left["definition"], right["definition"]
        # Same key is a candidate conflict. Different spellings/semantics need agent review.
        if a["key"] == b["key"] and normalized(a["value"]) != normalized(b["value"]):
            target = potential_conflicts if left["blockers"] or right["blockers"] else conflicts
            target.append(
                {
                    "key": a["key"],
                    "rule_ids": [a["rule_id"], b["rule_id"]],
                    "status": "needs_operator_decision",
                }
            )
    conflicted = {identifier for c in conflicts for identifier in c["rule_ids"]}
    for row in rows:
        if row["definition"]["rule_id"] in conflicted:
            row["blockers"].append("conflict")
    return {
        "client_id": workspace_info(root)["client_id"],
        "project": project,
        "as_of": str(on),
        "status_time": "current_registry",
        "rules": rows,
        "conflicts": conflicts,
        "potential_conflicts": potential_conflicts,
        "applicable": [r for r in rows if not r["blockers"]],
    }


def make_basis(root, identifiers, project, on, used_for):
    if not identifiers or len(set(identifiers)) != len(identifiers):
        fail("CONTEXT_BASIS", "Wskaż niepowtarzające się ID wykorzystanych ustaleń.")
    view = rules_view(root, project, on)
    available = {r["definition"]["rule_id"]: r for r in view["applicable"]}
    if not set(identifiers).issubset(available):
        fail("CONTEXT_BASIS", "Ustalenie jest nieaktualne, niepotwierdzone lub ma konflikt.")
    refs = {}
    for identifier in identifiers:
        for ref in available[identifier]["definition"]["sources"]:
            refs[ref["chunk_id"]] = ref
    return ContextBasis.model_validate_json(
        json.dumps(
            {
                "client_id": view["client_id"],
                "project": project,
                "as_of": str(on),
                "rule_ids": identifiers,
                "rules": [available[identifier]["definition"] for identifier in identifiers],
                "sources": list(refs.values()),
                "used_for": used_for,
            }
        )
    )


def verify_basis(root, basis, client_id, project=None):
    if basis.client_id != client_id or (project is not None and basis.project != project):
        fail("SCOPE_MISMATCH", "Podstawa rekomendacji dotyczy innego klienta lub projektu.")
    expected = make_basis(root, basis.rule_ids, basis.project, basis.as_of, basis.used_for)
    if sorted(r.model_dump_json() for r in basis.sources) != sorted(
        r.model_dump_json() for r in expected.sources
    ) or sorted(r.model_dump_json() for r in basis.rules) != sorted(
        r.model_dump_json() for r in expected.rules
    ):
        fail("CONTEXT_REFERENCE", "Podstawa rekomendacji nie zgadza się z ustaleniami.")


def compare_documents(root, before, after):
    left, right = document(root, before), document(root, after)
    if before == after or left["material"].get("project") != right["material"].get("project"):
        fail("CONTEXT_COMPARE", "Wskaż dwa różne materiały z tego samego projektu.")
    a, b = left["chunks"], right["chunks"]
    matcher = SequenceMatcher(a=[c["quote"] for c in a], b=[c["quote"] for c in b], autojunk=False)
    changes = [
        {"change": tag, "before": a[i:j], "after": b[k:end]}
        for tag, i, j, k, end in matcher.get_opcodes()
        if tag != "equal"
    ]
    return {
        "before": left["material"],
        "after": right["material"],
        "changes": changes,
        "warnings": left["warnings"] + right["warnings"],
        "reading_status": [left["status"], right["status"]],
        "meaning_review_required": True,
        "rules_changed": False,
    }


def meeting_pair(root, project=None):
    items = [
        x
        for x in context_index(root)["items"]
        if x.get("project") == project and x["type"] == "meeting"
    ]
    if len(items) < 2 or any(not x.get("document_date") for x in items):
        fail("CONTEXT_MEETINGS", "Wskaż dwa ID notatek lub dodaj daty spotkań przy imporcie.")
    items.sort(key=lambda x: x["document_date"], reverse=True)
    if sum(x["document_date"] >= items[1]["document_date"] for x in items) != 2:
        fail("CONTEXT_MEETINGS", "Kilka notatek ma tę samą datę; wskaż dwa ID do porównania.")
    if items[0]["document_date"] == items[1]["document_date"]:
        fail("CONTEXT_MEETINGS", "Notatki mają tę samą datę; wskaż dwa ID do porównania.")
    return items[1]["id"], items[0]["id"]
