"""Local goals and recommendations CLI; uses saved Meta snapshots only."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from meta_ads_manager import __version__
from meta_ads_manager.decision_models import DECISION_CONTRACTS
from meta_ads_manager.decision_store import Decisions, fail
from meta_ads_manager.goal_reporting import compare, evaluate, fixed_window, measurements
from meta_ads_manager.meta_provider import report_period, validate_scope
from meta_ads_manager.storage import Store


def add_commands(commands, scoped, period):
    for name, actions in (
        ("goals", ("set", "assign", "list", "show")),
        ("recommendations", ("add", "event", "list", "show", "evaluate")),
    ):
        sub = commands.add_parser(name).add_subparsers(dest="action", required=True)
        for action in actions:
            parser = sub.add_parser(action)
            scoped(parser)
            if action in ("set", "assign", "add", "event"):
                parser.add_argument("--file", type=Path, required=True)
            if action == "show":
                parser.add_argument("--id", required=True)
                parser.add_argument("--revision", type=int)
            if action == "list" and name == "recommendations":
                parser.add_argument("--due", action="store_true")
                parser.add_argument("--as-of", type=date.fromisoformat)
            if action == "evaluate":
                parser.add_argument("--id", required=True)
                parser.add_argument("--expected-revision", type=int, required=True)
                parser.add_argument("--snapshot", required=True)


def registry_path(args):
    return args.data_dir / "decisions.sqlite3"


def saved_snapshot(args):
    path = args.data_dir / "meta.sqlite3"
    if not path.is_file():
        fail("INSUFFICIENT_DATA", "Najpierw pobierz snapshot konta.")
    with Store(path) as store:
        return store.snapshot(args.client, args.account, getattr(args, "snapshot", None))


def dispatch_decisions(args):
    from meta_ads_manager.cli import no_duplicate_keys

    if args.demo:
        fail("SOURCE_MISMATCH", "Rejestry dotyczą Meta; demo ma osobne, stałe profile.")
    validate_scope(Path.cwd(), args.client, args.account)
    with Decisions(registry_path(args), args.client, args.account) as registry:
        if args.action in ("set", "assign", "add", "event"):
            raw = args.file.read_text(encoding="utf-8")
            json.loads(raw, object_pairs_hook=no_duplicate_keys)
            kinds = {
                "set": "business_goal",
                "assign": "campaign_goal_assignment",
                "add": "recommendation",
                "event": "recommendation_event",
            }
            model = DECISION_CONTRACTS[kinds[args.action]].model_validate_json(raw)
            registry.scope(model)
            if args.action in ("assign", "add"):
                _, snapshot = saved_snapshot(args)
                ids = [model.campaign_id] if args.action == "assign" else model.campaign_ids
                if not set(ids).issubset({c.campaign_id for c in snapshot.campaigns}):
                    fail(
                        "SCOPE_MISMATCH", "Nie znaleziono wskazanych kampanii w snapshotcie konta."
                    )
            method = {
                "set": registry.save_goal,
                "assign": registry.assign,
                "add": registry.add_recommendation,
                "event": registry.event,
            }[args.action]
            return method(model), []
        if args.action == "show":
            category = "goal" if args.command == "goals" else "recommendation"
            return registry.get(category, args.id, args.revision), []
        if args.action == "list":
            if args.command == "goals":
                return {
                    "client_id": args.client,
                    "account_id": args.account,
                    "records": [
                        r for r in registry.all() if r["category"] in ("goal", "assignment")
                    ],
                }, []
            return {
                "client_id": args.client,
                "account_id": args.account,
                "as_of": str(args.as_of or date.today()),
                "items": registry.recommendations(args.as_of, args.due),
            }, []
        row = registry.get("recommendation", args.id)
        snapshot_id, snapshot = saved_snapshot(args)
        if row["data"]["status"] == "evaluated" and (
            row["data"]["evaluation"]["snapshot_id"] == snapshot_id
            and args.expected_revision == row["revision"] - 1
        ):
            return row, []
        result = evaluate(snapshot_id, snapshot, registry, row)
        return registry.save_evaluation(args.id, args.expected_revision, result), []


def review_goal(args, snapshot_id, snapshot, registry):
    from meta_ads_manager.errors import AppError

    since, until = report_period(args, snapshot.spec.timezone, default_days=7)
    days = (until - since).days + 1
    previous_since, previous_until = since - timedelta(days=days), since - timedelta(days=1)
    records = registry.all()
    previous = measurements(snapshot, previous_since, previous_until, records)
    current = measurements(snapshot, since, until, records)
    groups = [g for g in current["groups"] if g["goal_id"] == args.goal]
    prior = [g for g in previous["groups"] if g["goal_id"] == args.goal]
    if not groups and not prior:
        fail("GOAL_REQUIRED", "Brak przypisanych kampanii tego celu w obu okresach.")
    comparisons = []
    keys = {(g["goal_id"], g["goal_revision"]) for g in groups + prior}
    for identifier, revision in sorted(keys):
        current_ids = {
            c for g in groups if g["goal_revision"] == revision for c in g["campaign_ids"]
        }
        prior_ids = {c for g in prior if g["goal_revision"] == revision for c in g["campaign_ids"]}
        if current_ids != prior_ids:
            comparisons.append(
                {
                    "goal_revision": revision,
                    "status": "not_comparable",
                    "reason": "campaign_cohort_changed",
                }
            )
            continue
        try:
            common = (snapshot, records, identifier, revision, sorted(current_ids))
            before = fixed_window(*common, previous_since, previous_until)
            after = fixed_window(*common, since, until)
        except AppError as exc:
            comparisons.append(
                {"goal_revision": revision, "status": "not_comparable", "reason": exc.code}
            )
            continue
        comparisons.append(
            {
                "goal_revision": revision,
                "campaign_ids": sorted(current_ids),
                "status": "comparable",
                "previous": before,
                "current": after,
                "relative_changes": compare(before, after),
            }
        )
    return {
        "schema_version": "1.0",
        "kind": "goal_review",
        "status": "SUCCEEDED",
        "generated_at": datetime.now(UTC).isoformat(),
        "data_fetched_at": snapshot.fetched_at.isoformat(),
        "limitations": [],
        "run_id": "review_" + uuid4().hex,
        "snapshot_id": snapshot_id,
        "client_id": snapshot.client_id,
        "account_id": snapshot.account_id,
        "source": "meta",
        "code_version": __version__,
        "goal_id": args.goal,
        "period": {"since": str(since), "until": str(until)},
        "previous_period": {"since": str(previous_since), "until": str(previous_until)},
        "report_spec": snapshot.spec.model_dump(mode="json"),
        "previous": prior,
        "current": groups,
        "comparisons": comparisons,
        "recommendation_history": registry.recommendations(),
        "recommendation_history_as_of": str(date.today()),
        "evidence_refs": [snapshot_id],
        "causal_effect_established": False,
    }
