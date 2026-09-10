"""Live source routing; report reads remain offline and scoped to the saved snapshot."""

from pathlib import Path

from meta_ads_manager.errors import AppError
from meta_ads_manager.meta_connection import load_connection
from meta_ads_manager.meta_provider import (
    MetaProvider,
    configured_clients,
    profile_from_snapshot,
    report_period,
    validate_scope,
)
from meta_ads_manager.reporting import account_audit, account_report
from meta_ads_manager.storage import Store


def dispatch_live(args) -> tuple[dict, list[dict]]:
    root = Path.cwd()
    if args.command == "clients":
        return {
            "source": "meta",
            "scope": "locally_configured",
            "clients": configured_clients(root),
        }, []
    if args.command == "accounts":
        connection = load_connection(root, args.client)
        if not connection.account_id:
            raise AppError("CONFIG_REQUIRED", "Brak ID konta w konfiguracji.", 3)
        profile = MetaProvider(root, args.client, connection.account_id).resolve()
        account = profile.accounts[0]
        return {
            "source": "meta",
            "scope": "locally_configured",
            "client_id": args.client,
            "accounts": [
                {
                    "account_id": account.account_id,
                    "name": profile.name,
                    "currency": account.currency,
                    "timezone": account.timezone,
                    "goals": [],
                }
            ],
        }, []
    if not args.client or not args.account:
        raise AppError("VALIDATION_ERROR", "Wymagane są --client i --account.", 2)
    validate_scope(root, args.client, args.account)
    if args.command == "analyze":
        raise AppError(
            "GOAL_REQUIRED",
            "Analiza celu Meta wymaga mapowania konwersji. "
            "Dostępne są report campaigns i częściowy audit.",
            2,
        )
    db_path = args.data_dir / "meta.sqlite3"
    if args.command == "sync" and args.action != "status":
        provider = MetaProvider(root, args.client, args.account)
        profile = provider.resolve()
        since, until = report_period(args, profile.accounts[0].timezone, default_days=30)
        snapshot = provider.fetch(since, until)
        with Store(db_path) as store:
            result = store.save_snapshot(snapshot)
        result.update(
            client_id=args.client,
            account_id=args.account,
            campaign_count=len(snapshot.campaigns),
            reconciliation=snapshot.meta.model_dump(mode="json"),
        )
        return result, []
    if not db_path.is_file():
        raise AppError("INSUFFICIENT_DATA", "Brak danych Meta; najpierw wykonaj sync.", 6)
    with Store(db_path) as store:
        if args.command == "report" and args.action == "show":
            result = store.report(args.client, args.account, args.run)
            if result["source"] != "meta":
                raise AppError("SCOPE_MISMATCH", "Raport pochodzi z innego źródła.", 3)
            return result, []
        run_id = args.run if args.command == "sync" else args.snapshot
        snapshot_id, snapshot = store.snapshot(args.client, args.account, run_id)
        if snapshot.source != "meta":
            raise AppError("SCOPE_MISMATCH", "Snapshot pochodzi z innego źródła.", 3)
        if args.command == "sync":
            return {
                "run_id": snapshot_id,
                "source": "meta",
                "status": "SUCCEEDED",
                "since": str(snapshot.since),
                "until": str(snapshot.until),
            }, []
        since, until = report_period(args, snapshot.spec.timezone)
        result = account_report(
            snapshot_id, snapshot, profile_from_snapshot(snapshot), since, until
        )
        if args.command == "audit":
            result = account_audit(result)
        store.save_report(result)
        return result, []
