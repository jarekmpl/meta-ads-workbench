import sqlite3
from datetime import date

import pytest

from meta_ads_manager.analytics import weekly_review
from meta_ads_manager.errors import AppError
from meta_ads_manager.provider import DemoProvider
from meta_ads_manager.storage import Store


def test_snapshot_versions_never_duplicate_facts_in_analysis(tmp_path):
    provider = DemoProvider()
    full = provider.available("demo-shop", "act_DEMO_SHOP")
    with Store(tmp_path / "test.sqlite3") as store:
        first = store.save_snapshot(full)
        second = store.save_snapshot(full)
        assert first["run_id"] != second["run_id"]
        assert first["content_hash"] == second["content_hash"]
        latest_id, latest = store.snapshot("demo-shop", "act_DEMO_SHOP")
        assert latest_id == second["run_id"]
        assert len(latest.facts) == len(full.facts)
        store.save_snapshot(
            provider.fetch("demo-shop", "act_DEMO_SHOP", date(2026, 9, 2), date(2026, 9, 8))
        )
        old_id, old = store.snapshot("demo-shop", "act_DEMO_SHOP", first["run_id"])
        assert old_id == first["run_id"]
        assert len(old.facts) == len(full.facts)


def test_reports_and_snapshots_cannot_cross_client_scope(tmp_path):
    provider = DemoProvider()
    with Store(tmp_path / "test.sqlite3") as store:
        saved = store.save_snapshot(provider.available("demo-shop", "act_DEMO_SHOP"))
        report = weekly_review(
            saved["run_id"],
            provider.available("demo-shop", "act_DEMO_SHOP"),
            provider.goal("demo-shop", "act_DEMO_SHOP", "commerce-pl"),
        )
        store.save_report(report)
        assert store.report("demo-shop", "act_DEMO_SHOP", report["run_id"]) == report
        with pytest.raises(AppError):
            store.snapshot("demo-leads", "act_DEMO_SHOP", saved["run_id"])
        with pytest.raises(AppError):
            store.report("demo-leads", "act_DEMO_LEADS", report["run_id"])
        report.update(client_id="demo-leads", account_id="act_DEMO_LEADS", run_id="foreign")
        with pytest.raises(sqlite3.IntegrityError):
            store.save_report(report)


def test_account_cannot_be_silently_reassigned(tmp_path):
    snapshot = DemoProvider().available("demo-shop", "act_DEMO_SHOP")
    with Store(tmp_path / "test.sqlite3") as store:
        store.save_snapshot(snapshot)
        snapshot.client_id = "demo-leads"
        with pytest.raises(AppError, match="właściciela"):
            store.save_snapshot(snapshot)
