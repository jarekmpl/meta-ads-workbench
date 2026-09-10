import json
import subprocess
import sys
from pathlib import Path

import pytest

from meta_ads_manager.cli import run

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def invoke(capsys, tmp_path):
    def call(*args, demo=True):
        prefix = ["--data-dir", str(tmp_path / "data")]
        if demo:
            prefix.append("--demo")
        code = run([*prefix, *args])
        capture = capsys.readouterr()
        assert capture.err == ""
        result = json.loads(capture.out)
        assert set(result) == {"schema_version", "request_id", "ok", "data", "warnings", "error"}
        return code, result

    return call


@pytest.mark.parametrize(
    "client,account,goal",
    [
        ("demo-leads", "act_DEMO_LEADS", "leads-pl"),
        ("demo-shop", "act_DEMO_SHOP", "commerce-pl"),
    ],
)
def test_complete_demo_flow(invoke, client, account, goal):
    scope = ["--client", client, "--account", account]
    code, sync = invoke("sync", *scope)
    assert code == 0 and sync["data"]["fact_count"] == 28
    code, status = invoke("sync", "status", *scope, "--run", sync["data"]["run_id"])
    assert code == 0 and status["data"]["status"] == "SUCCEEDED"
    code, analysis = invoke("analyze", *scope, "--goal", goal)
    assert code == 0 and analysis["data"]["source"] == "demo"
    code, report = invoke("report", "show", *scope, "--run", analysis["data"]["run_id"])
    assert code == 0 and report["data"] == analysis["data"]


def test_scope_is_checked_before_database_creation(invoke, tmp_path):
    code, response = invoke("sync", "--client", "demo-leads", "--account", "act_DEMO_SHOP")
    assert code == 3 and response["error"]["code"] == "SCOPE_MISMATCH"
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize(
    "args",
    [
        ["sync"],
        ["sync", "--client", "demo-shop", "--account", "act_DEMO_SHOP", "--last-days", "0"],
        ["sync", "--client", "demo-shop", "--account", "act_DEMO_SHOP", "--since", "2026-09-01"],
        [
            "sync",
            "--client",
            "demo-shop",
            "--account",
            "act_DEMO_SHOP",
            "--since",
            "2026-09-01",
            "--until",
            "2026-09-08",
            "--last-days",
            "7",
        ],
        ["sync", "--client", "demo-shop", "--account", "act_DEMO_SHOP", "--until", "not-a-date"],
        ["--token", "DO_NOT_PRINT_THIS_SECRET"],
        ["changes", "apply", "DO_NOT_PRINT_THIS_SECRET"],
    ],
)
def test_input_errors_are_json_and_do_not_echo_inputs(invoke, args):
    code, result = invoke(*args)
    assert code == 2 and not result["ok"]
    assert "DO_NOT_PRINT_THIS_SECRET" not in json.dumps(result)


def test_demo_must_be_explicit_and_missing_data_is_actionable(invoke, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    code, result = invoke("clients", "list", demo=False)
    assert code == 0 and result["data"]["clients"] == []
    code, result = invoke(
        "analyze", "--client", "demo-shop", "--account", "act_DEMO_SHOP", "--goal", "commerce-pl"
    )
    assert code == 6 and result["error"]["code"] == "INSUFFICIENT_DATA"


def test_validation_redacts_secret_values_and_duplicate_keys(invoke, tmp_path):
    raw = json.loads((ROOT / "examples/client-profile.json").read_text())
    raw["token"] = "DO_NOT_PRINT_THIS_SECRET"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw))
    code, result = invoke("validate", "--file", str(path), demo=False)
    assert code == 2 and "DO_NOT_PRINT_THIS_SECRET" not in json.dumps(result)
    path.write_text('{"kind":"client_profile", "kind":"change_proposal"}')
    code, result = invoke("validate", "--file", str(path), demo=False)
    assert code == 2


def test_output_is_standalone_json_and_is_not_overwritten(invoke, tmp_path):
    path = tmp_path / "schema.json"
    code, result = invoke("--output", str(path), "schema", "export", "--kind", "client_profile")
    assert code == 0
    assert json.loads(path.read_text()) == result["data"]
    before = path.read_bytes()
    code, result = invoke("--output", str(path), "clients", "list")
    assert code == 2 and result["error"]["code"] == "OUTPUT_EXISTS"
    assert path.read_bytes() == before


def test_installed_module_works_outside_repository(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "meta_ads_manager", "--demo", "clients", "list"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert len(json.loads(result.stdout)["data"]["clients"]) == 2


def test_agent_workflow_for_thirty_day_report_and_multiple_audits(invoke):
    code, capability = invoke("capabilities", demo=False)
    assert code == 0 and capability["data"]["sources"] == {"demo": True, "meta": True}
    reports = []
    for client, account in [("demo-shop", "act_DEMO_SHOP"), ("demo-leads", "act_DEMO_LEADS")]:
        scope = ["--client", client, "--account", account]
        code, sync = invoke("sync", *scope, "--last-days", "30")
        assert code == 0 and sync["data"]["fact_count"] == 60
        snapshot = sync["data"]["run_id"]
        code, report = invoke(
            "report", "campaigns", *scope, "--last-days", "30", "--snapshot", snapshot
        )
        assert code == 0 and report["data"]["campaign_count"] == 2
        code, audit = invoke("audit", *scope, "--last-days", "30", "--snapshot", snapshot)
        assert code == 0 and audit["data"]["status"] == "PARTIAL"
        assert audit["data"]["client_id"] == client
        code, reread = invoke("report", "show", *scope, "--run", audit["data"]["run_id"])
        assert code == 0 and reread["data"] == audit["data"]
        reports.append(report["data"])
    assert reports[0]["snapshot_id"] != reports[1]["snapshot_id"]


def test_thirty_day_report_requires_full_data_even_with_short_snapshot(invoke):
    scope = ["--client", "demo-shop", "--account", "act_DEMO_SHOP"]
    code, _ = invoke("sync", *scope)  # Default is still fourteen days.
    assert code == 0
    code, report = invoke("report", "campaigns", *scope, "--last-days", "30")
    assert code == 6 and report["error"]["code"] == "INSUFFICIENT_DATA"
