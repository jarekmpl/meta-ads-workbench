"""Portable context commands shared by Codex, Claude Code and Antigravity."""

import json
from datetime import date
from pathlib import Path

from meta_ads_manager.context_engine import (
    add_rule,
    compare_documents,
    document,
    make_basis,
    meeting_pair,
    rule_status,
    rules_view,
    search,
)
from meta_ads_manager.context_models import ContextRule
from meta_ads_manager.workspace import confined


def add_commands(sub):
    read = sub.add_parser("read", help="Odczytaj tekst i odwołania do fragmentów")
    read.add_argument("--id", required=True)
    find = sub.add_parser("search", help="Wyszukaj fragmenty w materiałach klienta")
    find.add_argument("--query", required=True)
    find.add_argument("--limit", type=int, default=10)
    find.add_argument("--history", action="store_true")
    rules = sub.add_parser("rules", help="Aktualne ustalenia i konflikty")
    add = sub.add_parser("rule-add", help="Zapisz ustalenie jako propozycję")
    add.add_argument("--file", type=Path, required=True)
    state = sub.add_parser("rule-status", help="Zapisz decyzję operatora o ustaleniu")
    state.add_argument("--id", required=True)
    state.add_argument("--status", choices=("confirmed", "retired"), required=True)
    state.add_argument("--expected-revision", type=int, required=True)
    state.add_argument("--actor", required=True)
    state.add_argument("--reason", required=True)
    compare = sub.add_parser("compare", help="Porównaj dwie wersje materiału")
    compare.add_argument("--before", required=True)
    compare.add_argument("--after", required=True)
    meetings = sub.add_parser("meetings", help="Porównaj dwa ostatnie datowane spotkania")
    basis = sub.add_parser("basis", help="Przygotuj podstawę rekomendacji")
    basis.add_argument("--rule", action="append", required=True)
    basis.add_argument("--used-for", required=True)
    for parser in (find, rules, basis):
        parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    for parser in (find, rules, basis, meetings):
        parser.add_argument("--project")
    for parser in (read, find, rules, add, state, compare, meetings, basis):
        parser.add_argument("--output", type=Path)


def dispatch(root, args):
    if args.action == "read":
        return document(root, args.id)
    if args.action == "search":
        return search(root, args.query, args.project, args.as_of, args.limit, args.history)
    if args.action == "rules":
        return rules_view(root, args.project, args.as_of)
    if args.action == "rule-add":
        from meta_ads_manager.cli import no_duplicate_keys

        path = confined(root, args.file)
        raw = path.read_text(encoding="utf-8")
        json.loads(raw, object_pairs_hook=no_duplicate_keys)
        return add_rule(root, ContextRule.model_validate_json(raw))
    if args.action == "rule-status":
        return rule_status(
            root, args.id, args.status, args.expected_revision, args.actor, args.reason
        )
    if args.action == "compare":
        return compare_documents(root, args.before, args.after)
    if args.action == "meetings":
        return compare_documents(root, *meeting_pair(root, args.project))
    if args.action == "basis":
        return make_basis(root, args.rule, args.project, args.as_of, args.used_for).model_dump(
            mode="json"
        )
    raise ValueError("Unknown context command")
