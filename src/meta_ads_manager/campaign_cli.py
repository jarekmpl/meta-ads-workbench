"""Conversational campaign wizard commands shared by all LLM clients."""

import json
from pathlib import Path

from meta_ads_manager.campaign_api import CampaignAPI
from meta_ads_manager.campaign_executor import execute, record_approval, validate_plan
from meta_ads_manager.campaign_models import WizardAnswer, WizardApproval
from meta_ads_manager.campaign_planner import compile_plan, complete, plan_markdown
from meta_ads_manager.campaign_store import WizardStore
from meta_ads_manager.campaign_website import collect
from meta_ads_manager.decision_models import CampaignGoalAssignment
from meta_ads_manager.decision_store import Decisions, canonical, fail
from meta_ads_manager.meta_connection import load_credentials
from meta_ads_manager.meta_provider import validate_scope


def add_commands(commands, scoped):
    wizard = commands.add_parser("wizard", help="Kreator kampanii, plan i kontrolowane tworzenie.")
    sub = wizard.add_subparsers(dest="action", required=True)
    for action in (
        "start",
        "answer",
        "show",
        "list",
        "website",
        "discover",
        "plan",
        "plan-show",
        "approve",
        "execute",
        "reconcile",
        "status",
    ):
        parser = sub.add_parser(action)
        scoped(parser)
        if action == "start":
            parser.add_argument("--project", required=True)
        if action in ("answer", "approve"):
            parser.add_argument("--file", type=Path, required=True)
        if action in ("show", "website", "discover", "plan"):
            parser.add_argument("--id", required=True)
        if action in ("plan-show", "execute", "reconcile", "status"):
            parser.add_argument("--plan-hash", required=True)
        if action == "website":
            parser.add_argument("--url", required=True)
        if action in ("plan", "plan-show"):
            parser.add_argument("--preview", type=Path)


def goal_for(args, brief):
    with Decisions(args.data_dir / "decisions.sqlite3", args.client, args.account) as goals:
        row = goals.get("goal", brief.goal_id, brief.goal_revision)
    goal = row["data"]
    expected = {
        "lead_form": "onsite_conversion.lead_grouped",
        "web_lead": "offsite_conversion.fb_pixel_lead",
        "purchase": "offsite_conversion.fb_pixel_purchase",
        "registration": "offsite_conversion.fb_pixel_complete_registration",
        "custom_proxy": f"offsite_conversion.custom.{brief.custom_conversion_id}",
    }[brief.measurement]
    role = "proxy" if brief.measurement == "custom_proxy" else "primary"
    if (goal["project_id"], goal["currency"], goal["action_type"], goal["measurement_role"]) != (
        brief.project_id,
        brief.currency,
        expected,
        role,
    ):
        fail(
            "GOAL_INCOMPATIBLE",
            "Wybrany cel nie odpowiada projektowi, walucie lub zdarzeniu optymalizacji.",
        )
    return row


def link_created_goal(args, store, plan, result):
    if result["status"] != "SUCCEEDED":
        return result
    accepted = [
        r
        for r in store.all()
        if r["category"] == "approval"
        and r["id"] == plan["plan_hash"]
        and r["data"]["decision"] == "approve"
    ]
    if not accepted:
        fail("APPROVAL_REQUIRED", "Brak pierwotnej akceptacji planu.")
    brief = plan["brief"]
    assignment = CampaignGoalAssignment.model_validate_json(
        canonical(
            {
                "schema_version": "1.0",
                "kind": "campaign_goal_assignment",
                "client_id": args.client,
                "account_id": args.account,
                "campaign_id": result["ids"][plan["keys"]["campaign"]],
                "goal_id": brief["goal_id"],
                "goal_revision": brief["goal_revision"],
                "effective_from": brief["start_time"][:10],
                "expected_revision": 0,
                "confirmed_by": accepted[-1]["data"]["operator_name"],
                "confirmation_ref": "wizard:" + plan["plan_hash"],
            }
        )
    )
    with Decisions(args.data_dir / "decisions.sqlite3", args.client, args.account) as goals:
        binding = goals.assign(assignment)
    return {**result, "goal_assignment": binding}


def dispatch_wizard(args):
    from meta_ads_manager.cli import no_duplicate_keys
    from meta_ads_manager.workspace import confined, workspace_info

    if args.demo:
        fail("SOURCE_MISMATCH", "Kreator wymaga jawnego konta Meta. Testy syntetyczne są osobne.")
    connection = validate_scope(Path.cwd(), args.client, args.account)

    def api():
        return CampaignAPI(connection, load_credentials(Path.cwd(), connection))

    if getattr(args, "preview", None):
        if workspace_info(Path.cwd(), required=False):
            confined(Path.cwd(), args.preview, output=True)
        if args.preview.exists():
            fail("OUTPUT_EXISTS", "Podgląd już istnieje; wybierz nową nazwę.")
    with WizardStore(args.data_dir / "campaign-wizard.sqlite3", args.client, args.account) as store:
        action = args.action
        if action == "start":
            return store.describe(store.start(args.project)), []
        if action == "list":
            latest = {}
            for row in store.all():
                if row["category"] == "draft":
                    latest[row["id"]] = row
            return {"drafts": [store.describe(r) for r in latest.values()]}, []
        if action in ("answer", "approve"):
            raw = args.file.read_text()
            json.loads(raw, object_pairs_hook=no_duplicate_keys)
            if action == "answer":
                return store.describe(store.answer(WizardAnswer.model_validate_json(raw))), []
            approval = WizardApproval.model_validate_json(raw)
            plan = store.get("plan", approval.plan_hash)["data"]
            return record_approval(store, plan, approval), []
        if action in ("plan-show", "execute", "reconcile", "status"):
            plan = store.get("plan", args.plan_hash)["data"]
            if action == "status":
                approvals = [
                    r
                    for r in store.all()
                    if r["category"] == "approval" and r["id"] == args.plan_hash
                ]
                return {
                    **store.execution(args.plan_hash),
                    "approval": approvals[-1] if approvals else None,
                }, []
            if action in ("execute", "reconcile"):
                if action == "execute" and connection.access_mode != "approved_create_paused":
                    fail(
                        "READ_ONLY_VIOLATION",
                        "Konfiguracja klienta ma access_mode=read_only. "
                        "Włączenie wykonawcy wymaga jawnej decyzji "
                        "operatora.",
                    )
                result = execute(
                    store,
                    plan,
                    api,
                    args.data_dir / f"wizard-{args.account}.lock",
                    reconcile_only=action == "reconcile",
                )
                return link_created_goal(args, store, plan, result), []
        else:
            row = store.get("draft", args.id)
            if action == "show":
                return store.describe(row), []
            if action == "website":
                evidence = collect(args.url)
                return store.describe(
                    store.evidence(args.id, row["revision"], "website_evidence", evidence)
                ), []
            if action == "discover":
                selected = row["data"]["fields"].get("page_id", {}).get("value")
                evidence = api().inventory(selected)
                return store.describe(
                    store.evidence(args.id, row["revision"], "resource_evidence", evidence)
                ), []
            brief = complete(row["data"])
            goal = goal_for(args, brief)
            prior = [
                r["data"]
                for r in store.all()
                if r["category"] == "plan"
                and r["data"]["draft_id"] == args.id
                and r["data"]["draft_revision"] == row["revision"]
            ]
            if prior:
                plan = prior[-1]
                validate_plan(store, plan)
            else:
                resources = api().preflight(brief)
                keys = store.reserve(args.id, row["revision"], brief)
                plan = compile_plan(
                    brief,
                    keys,
                    draft_id=args.id,
                    revision=row["revision"],
                    api_version=connection.api_version,
                    resources=resources,
                    goal=goal,
                )
                store.save_plan(plan)
        if getattr(args, "preview", None):
            args.preview.parent.mkdir(parents=True, exist_ok=True)
            with args.preview.open("x", encoding="utf-8") as output:
                output.write(plan_markdown(plan))
        return plan, []
