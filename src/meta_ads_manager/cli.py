"""JSON-first CLI. Read-only Meta and explicit offline demo sources."""

import argparse
import json
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from meta_ads_manager import __version__
from meta_ads_manager.account_policy import account_change_policy
from meta_ads_manager.analytics import weekly_review
from meta_ads_manager.campaign_models import CAMPAIGN_CONTRACTS
from meta_ads_manager.context_models import ContextRule
from meta_ads_manager.decision_models import DECISION_CONTRACTS
from meta_ads_manager.errors import AppError
from meta_ads_manager.live_cli import dispatch_live
from meta_ads_manager.meta_connection import (
    Connection,
    check_connection,
    config_path,
    connection_status,
    save_private,
    store_credentials,
)
from meta_ads_manager.models import CONTRACTS
from meta_ads_manager.pdf_models import PdfDocument, PdfNotes
from meta_ads_manager.provider import DemoProvider
from meta_ads_manager.reporting import account_audit, account_report
from meta_ads_manager.storage import Store

SUPPORTED_CONTRACTS = {
    **CONTRACTS,
    **DECISION_CONTRACTS,
    **CAMPAIGN_CONTRACTS,
    "pdf_document": PdfDocument,
    "pdf_notes": PdfNotes,
    "context_rule": ContextRule,
}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse messages can echo user-supplied values (including accidental secrets).
        raise AppError("VALIDATION_ERROR", "Niepoprawne argumenty. Sprawdź --help.", 2)


def iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected YYYY-MM-DD") from exc


def positive_days(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected positive integer") from exc
    if not 1 <= result <= 3660:
        raise argparse.ArgumentTypeError("Days outside supported range")
    return result


def parser() -> Parser:
    root = Parser(description="Meta Ads Manager — raporty Meta i lokalne demo.")
    root.add_argument("--version", action="version", version=__version__)
    root.add_argument("--demo", action="store_true", help="Użyj wyłącznie danych syntetycznych.")
    root.add_argument("--data-dir", type=Path, default=Path("data"))
    root.add_argument("--format", choices=("json", "text"), default="json")
    root.add_argument(
        "--output", type=Path, help="Zapisz data odpowiedzi jako JSON (bez nadpisania)."
    )
    commands = root.add_subparsers(dest="command", required=True)

    def scoped(command, required=True):
        command.add_argument("--client", required=required)
        command.add_argument("--account", required=required)

    def period(command):
        command.add_argument("--last-days", type=positive_days)
        command.add_argument("--since", type=iso_date)
        command.add_argument("--until", type=iso_date)

    from meta_ads_manager.decision_cli import add_commands

    add_commands(commands, scoped, period)
    from meta_ads_manager.campaign_cli import add_commands as add_wizard

    add_wizard(commands, scoped)
    commands.add_parser("capabilities", help="Dostępne funkcje i źródła danych dla agenta.")
    auth = commands.add_parser("auth", help="Konfiguracja i test połączenia z prawdziwym kontem.")
    auth_commands = auth.add_subparsers(dest="action", required=True)
    auth_init = auth_commands.add_parser("init")
    auth_init.add_argument("--client", required=True)
    auth_init.add_argument("--app-id")
    auth_init.add_argument("--business-id")
    auth_init.add_argument("--account")
    auth_init.add_argument("--api-version")
    for name in ("status", "check", "store-token"):
        command = auth_commands.add_parser(name)
        command.add_argument("--client", required=True)
        if name == "store-token":
            command.add_argument("--with-app-secret", action="store_true")

    clients = commands.add_parser("clients", help="Lista skonfigurowanych klientów.")
    clients.add_subparsers(dest="action", required=True).add_parser("list")
    accounts = commands.add_parser("accounts", help="Konta jednego klienta.")
    accounts_list = accounts.add_subparsers(dest="action", required=True).add_parser("list")
    accounts_list.add_argument("--client", required=True)

    sync = commands.add_parser("sync", help="Pobierz i zapisz nowy snapshot danych.")
    scoped(sync, required=False)
    sync.add_argument("--last-days", type=positive_days)
    sync.add_argument("--since", type=iso_date)
    sync.add_argument("--until", type=iso_date)
    sync_status = sync.add_subparsers(dest="action").add_parser("status")
    scoped(sync_status)
    sync_status.add_argument("--run", required=True)

    analyze = commands.add_parser("analyze", help="Porównaj ostatnie dwa pełne tygodnie snapshotu.")
    scoped(analyze)
    analyze.add_argument("--recipe", choices=("weekly-review",), default="weekly-review")
    analyze.add_argument("--goal", required=True)
    analyze.add_argument("--snapshot", help="Odtwórz analizę na wskazanej wersji danych.")
    period(analyze)

    report = commands.add_parser("report", help="Odczytaj zapisany raport.")
    report_commands = report.add_subparsers(dest="action", required=True)
    show = report_commands.add_parser("show")
    scoped(show)
    show.add_argument("--run", required=True)
    campaigns = report_commands.add_parser("campaigns", help="Wszystkie kampanie w okresie.")
    scoped(campaigns)
    period(campaigns)
    campaigns.add_argument("--snapshot")

    audit = commands.add_parser("audit", help="Audyt konta z jawnym zakresem dostępnych danych.")
    scoped(audit)
    period(audit)
    audit.add_argument("--snapshot")

    validate = commands.add_parser(
        "validate", help="Walidacja struktury JSON, bez połączenia z API."
    )
    validate.add_argument("--file", type=Path, required=True)
    schema = commands.add_parser("schema", help="JSON Schema wygenerowane z modeli.")
    export = schema.add_subparsers(dest="action", required=True).add_parser("export")
    export.add_argument("--kind", choices=tuple(SUPPORTED_CONTRACTS), required=True)
    pdf = commands.add_parser("pdf", help="Eksport zapisanych raportów do PDF Bluerank.")
    pdf_commands = pdf.add_subparsers(dest="action", required=True)
    pdf_export = pdf_commands.add_parser("export")
    scoped(pdf_export)
    pdf_export.add_argument("--input", type=Path, required=True)
    pdf_export.add_argument("--pdf", type=Path, required=True)
    pdf_export.add_argument("--notes", type=Path)
    pdf_render = pdf_commands.add_parser("render")
    pdf_render.add_argument("--pdf", type=Path, required=True)
    pdf_render.add_argument("--directory", type=Path, required=True)
    pdf_render.add_argument("--dpi", type=int, default=110)
    creatives = commands.add_parser("creatives", help="Pilotaż analizy materiałów reklamowych.")
    creative_commands = creatives.add_subparsers(dest="action", required=True)
    collect = creative_commands.add_parser("collect")
    scoped(collect)
    period(collect)
    collect.add_argument("--sample-size", type=int, default=20)
    collect.add_argument("--directory", type=Path, required=True)
    media = creative_commands.add_parser("media")
    scoped(media)
    media.add_argument("--directory", type=Path, required=True)
    creative_report = creative_commands.add_parser("report")
    scoped(creative_report)
    creative_report.add_argument("--directory", type=Path, required=True)
    creative_report.add_argument("--assessment", type=Path, required=True)
    creative_report.add_argument("--notes", type=Path, required=True)
    return root


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AppError("VALIDATION_ERROR", "Powtórzone pole w pliku JSON.", 2)
        result[key] = value
    return result


def dispatch(args) -> tuple[dict, list[dict]]:
    if args.command == "wizard":
        from meta_ads_manager.campaign_cli import dispatch_wizard

        return dispatch_wizard(args)
    if args.command in ("goals", "recommendations"):
        from meta_ads_manager.decision_cli import dispatch_decisions

        return dispatch_decisions(args)
    if args.command == "creatives":
        from meta_ads_manager.creative_review import collect

        if args.demo:
            raise AppError("VALIDATION_ERROR", "Pilotaż kreacji wymaga źródła Meta.", 2)
        if args.action == "media":
            from meta_ads_manager.creative_media import collect_media

            return collect_media(args), []
        if args.action == "report":
            from meta_ads_manager.creative_report import render_report

            return render_report(args), []
        return collect(args), []
    if args.command == "pdf":
        from meta_ads_manager.pdf_export import export_pdf, render_pdf

        if args.demo:
            raise AppError("VALIDATION_ERROR", "Źródło PDF wynika z pliku, nie z flagi --demo.", 2)
        if args.action == "render":
            return render_pdf(args.pdf, args.directory, args.dpi), []
        return export_pdf(args.input, args.pdf, args.client, args.account, args.notes), []
    if args.command == "auth":
        if args.demo:
            raise AppError(
                "VALIDATION_ERROR", "Polecenia auth dotyczą połączenia Meta, nie demo.", 2
            )
        root = Path.cwd()
        if args.action == "init":
            connection = Connection(
                client_id=args.client,
                app_id=args.app_id,
                business_id=args.business_id,
                account_id=args.account,
                api_version=args.api_version,
            )
            save_private(config_path(root, args.client), connection.model_dump(mode="json"))
            return connection_status(root, args.client), []
        if args.action == "status":
            return connection_status(root, args.client), []
        if args.action == "store-token":
            return store_credentials(root, args.client, with_app_secret=args.with_app_secret), []
        return check_connection(root, args.client), []
    if args.command == "capabilities":
        provider = DemoProvider()
        return {
            "version": __version__,
            "sources": {"demo": True, "meta": True},
            "writes": True,
            "write_scope": "approved_new_campaigns_adsets_creatives_ads_paused",
            "campaign_wizard": True,
            "campaign_wizard_default_access": "read_only",
            "campaign_wizard_formats": ["existing_account_image"],
            "campaign_wizard_placements": ["facebook_feed"],
            "account_change_policy": account_change_policy(),
            "meta_connection_setup": True,
            "operator_workspaces": True,
            "client_context_registry": True,
            "client_context_readers": ["pdf_text", "docx_body_tables", "txt_utf8", "md_utf8"],
            "client_context_search": "local_lexical",
            "client_context_conflicts": "grounded_same_key_operator_resolution",
            "client_context_compare": True,
            "recommendation_context_basis": True,
            "client_context_ocr": False,
            "meta_reporting": True,
            "meta_goal_mapping": True,
            "meta_weekly_review": True,
            "goal_mapping_mode": "explicit_versioned_campaign_assignments",
            "recommendation_registry": True,
            "recommendation_evaluation": "saved_snapshot_before_after",
            "scheduled_reviews": False,
            "meta_account_discovery": "locally_configured",
            "audit_coverage": "partial",
            "creative_pilot": True,
            "creative_automated_visual_review": False,
            "pdf_export": True,
            "pdf_dependency_extra": "pdf",
            "pdf_visual_review_required": True,
            "commands": [
                "wizard start",
                "wizard answer",
                "wizard show",
                "wizard list",
                "wizard website",
                "wizard discover",
                "wizard plan",
                "wizard plan-show",
                "wizard approve",
                "wizard execute",
                "wizard reconcile",
                "wizard status",
                "goals set",
                "goals assign",
                "goals list",
                "goals show",
                "recommendations add",
                "recommendations event",
                "recommendations list",
                "recommendations show",
                "recommendations evaluate",
                "clients list",
                "accounts list",
                "sync",
                "sync status",
                "analyze",
                "report campaigns",
                "report show",
                "audit",
                "validate",
                "schema export",
                "auth init",
                "auth status",
                "auth store-token",
                "auth check",
                "pdf export",
                "pdf render",
                "creatives collect",
                "creatives media",
                "creatives report",
            ],
            "demo_accounts": [
                {
                    "client_id": s.client_id,
                    "account_id": s.account_id,
                    "since": str(s.since),
                    "until": str(s.until),
                }
                for s in provider.dataset.snapshots
            ],
            "relative_dates": "demo: end of dataset; meta: yesterday in account timezone",
        }, []
    if args.command == "schema":
        return SUPPORTED_CONTRACTS[args.kind].model_json_schema(), []
    if args.command == "validate":
        raw = args.file.read_text(encoding="utf-8")
        parsed = json.loads(raw, object_pairs_hook=no_duplicate_keys)
        kind = parsed.get("kind") if isinstance(parsed, dict) else None
        if not isinstance(kind, str) or kind not in SUPPORTED_CONTRACTS:
            raise AppError("VALIDATION_ERROR", "Nieznany rodzaj kontraktu JSON.", 2)
        model = SUPPORTED_CONTRACTS[kind].model_validate_json(raw)
        return {
            "kind": model.kind,
            "valid": True,
            "validation_scope": "local_contract_only",
            "execution_ready": False,
        }, [
            {
                "code": "LOCAL_VALIDATION_ONLY",
                "message": "Nie sprawdzono dostępu, zasobów API ani upoważnienia do wykonania.",
            }
        ]

    if not args.demo:
        return dispatch_live(args)
    provider = DemoProvider()
    warnings = [
        {
            "code": "DEMO_DATA",
            "message": "Dane syntetyczne ze stałego okresu; nie pochodzą z kont reklamowych.",
        }
    ]
    if args.command == "clients":
        return {
            "clients": [
                {"client_id": p.client_id, "name": p.name} for p in provider.dataset.profiles
            ]
        }, warnings
    if args.command == "accounts":
        profile = provider.client(args.client)
        return {
            "client_id": profile.client_id,
            "accounts": [
                {
                    "account_id": a.account_id,
                    "currency": a.currency,
                    "timezone": a.timezone,
                    "goals": [
                        g.goal_id
                        for p in profile.projects
                        if a.account_id in p.account_ids
                        for g in p.goal_profiles
                    ],
                }
                for a in profile.accounts
            ],
        }, warnings

    if not args.client or not args.account:
        raise AppError("VALIDATION_ERROR", "Wymagane są --client i --account.", 2)
    profile, _ = provider.resolve(args.client, args.account)
    db_path = args.data_dir / "demo.sqlite3"
    if args.command == "sync" and args.action != "status":
        if (args.since is None) != (args.until is None):
            raise AppError("VALIDATION_ERROR", "Podaj razem --since i --until.", 2)
        if args.last_days is not None and args.since is not None:
            raise AppError("VALIDATION_ERROR", "Nie łącz --last-days z konkretnymi datami.", 2)
        available = provider.available(args.client, args.account)
        until = args.until or available.until
        since = args.since or (until - timedelta(days=(args.last_days or 14) - 1))
        snapshot = provider.fetch(args.client, args.account, since, until)
        with Store(db_path) as store:
            return store.save_snapshot(snapshot), warnings

    # Read commands do not create an empty database when sync has not been run.
    if not db_path.is_file():
        raise AppError("INSUFFICIENT_DATA", "Brak lokalnych danych; najpierw wykonaj sync.", 6)
    if args.command == "analyze":
        if args.since is not None or args.until is not None or args.last_days is not None:
            raise AppError("VALIDATION_ERROR", "Analiza demo ma stały okres; nie podawaj dat.", 2)
        goal = provider.goal(args.client, args.account, args.goal)
        with Store(db_path) as store:
            snapshot_id, snapshot = store.snapshot(args.client, args.account, args.snapshot)
            result = weekly_review(snapshot_id, snapshot, goal)
            store.save_report(result)
            return result, warnings
    if args.command == "audit" or (args.command == "report" and args.action == "campaigns"):
        with Store(db_path) as store:
            snapshot_id, snapshot = store.snapshot(args.client, args.account, args.snapshot)
            if (args.since is None) != (args.until is None):
                raise AppError("VALIDATION_ERROR", "Podaj razem --since i --until.", 2)
            if args.last_days is not None and args.since is not None:
                raise AppError("VALIDATION_ERROR", "Nie łącz --last-days z konkretnymi datami.", 2)
            until = args.until or snapshot.until
            since = args.since or (until - timedelta(days=(args.last_days or 30) - 1))
            result = account_report(snapshot_id, snapshot, profile, since, until)
            if args.command == "audit":
                result = account_audit(result)
            store.save_report(result)
            return result, warnings
    with Store(db_path) as store:
        if args.command == "sync":
            run_id, snapshot = store.snapshot(args.client, args.account, args.run)
            return {
                "run_id": run_id,
                "status": "SUCCEEDED",
                "source": snapshot.source,
                "since": str(snapshot.since),
                "until": str(snapshot.until),
            }, warnings
        return store.report(args.client, args.account, args.run), warnings


def write_artifact(path: Path, data: dict) -> None:
    """Publish a complete JSON file without overwriting an existing artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as temporary:
            temp_path = Path(temporary.name)
            json.dump(data, temporary, ensure_ascii=False, allow_nan=False, indent=2)
            temporary.write("\n")
        os.link(temp_path, path)
    except FileExistsError as exc:
        raise AppError(
            "OUTPUT_EXISTS", "Plik wynikowy już istnieje; wybierz nową nazwę.", 2
        ) from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def render_text(envelope: dict) -> str:
    if not envelope["ok"]:
        return f"{envelope['error']['code']}: {envelope['error']['message']}"
    data = envelope["data"]
    lines = [warning["message"] for warning in envelope["warnings"]]
    if data.get("kind") == "analysis_report":
        period = data["periods"]["current"]
        lines.extend(
            [
                f"Raport: {data['run_id']}",
                f"Klient: {data['client_id']} | Konto: {data['account_id']} "
                f"| Cel: {data['goal_id']}",
                f"Okres: {period['since']} — {period['until']}",
            ]
        )
        for name, value in data["summary"]["current"]["metrics"].items():
            lines.append(
                f"{name}: {value['value'] or 'brak'} {value['unit']}"
                + (f" ({value['reason']})" if value["reason"] else "")
            )
        lines.extend(data["limitations"])
    else:
        lines.append(json.dumps(data, ensure_ascii=False, indent=2))
    return "\n".join(lines)


def run(argv: list[str] | None = None) -> int:
    envelope = {
        "schema_version": "1.0",
        "request_id": f"req_{uuid4().hex}",
        "ok": False,
        "data": None,
        "warnings": [],
        "error": None,
    }
    args = None
    code = 0
    try:
        args = parser().parse_args(argv)
        from meta_ads_manager.workspace import guard_cli

        guard_cli(args, Path.cwd())
        if args.output is not None and args.output.exists():
            raise AppError("OUTPUT_EXISTS", "Plik wynikowy już istnieje; wybierz nową nazwę.", 2)
        data, warnings = dispatch(args)
        if args.output is not None:
            write_artifact(args.output, data)
        envelope.update(ok=True, data=data, warnings=warnings)
    except AppError as exc:
        envelope["error"], code = exc.as_dict(), exc.exit_code
    except (ValidationError, json.JSONDecodeError, UnicodeError):
        envelope["error"] = AppError(
            "VALIDATION_ERROR", "Dane nie spełniają kontraktu JSON.", 2
        ).as_dict()
        code = 2
    except OSError:
        envelope["error"] = AppError(
            "FILE_ERROR", "Nie można odczytać lub zapisać pliku.", 1
        ).as_dict()
        code = 1
    except Exception:
        # Deliberately never echo raw SDK/validation/database exceptions or inputs.
        envelope["error"] = AppError("INTERNAL_ERROR", "Wewnętrzny błąd aplikacji.", 1).as_dict()
        code = 1
    if args is not None and args.format == "text":
        print(render_text(envelope))
    else:
        print(json.dumps(envelope, ensure_ascii=False, allow_nan=False))
    return code


def main() -> None:
    sys.exit(run())
