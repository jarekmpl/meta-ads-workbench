import argparse
import importlib.util
import json
from pathlib import Path

import pytest

from meta_ads_manager.cli import run as meta_run
from meta_ads_manager.errors import AppError
from meta_ads_manager.workspace import (
    add_context,
    context_items,
    context_lock,
    guard_cli,
    run,
    set_context_status,
)


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


def args(**kwargs):
    return argparse.Namespace(demo=False, data_dir=Path("data"), **kwargs)


def test_wrong_client_fails_before_api(client, capsys):
    assert meta_run(["auth", "check", "--client", "client-b"]) == 3
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "SCOPE_MISMATCH"
    assert not (client / "data").exists()


def test_wrong_account_fails_before_api(client, capsys):
    assert meta_run(["auth", "init", "--client", "client-a", "--account", "act_123"]) == 0
    capsys.readouterr()
    assert meta_run(["sync", "--client", "client-a", "--account", "act_456"]) == 3
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "SCOPE_MISMATCH"


@pytest.mark.parametrize(
    "options",
    [
        {"output": Path("../other/report.json")},
        {"input": Path("../other/private.json")},
        {"output": Path("config/local/override.json")},
        {"file": Path("secrets/token.json")},
        {"directory": Path("../other")},
    ],
)
def test_path_escape_blocked(client, options):
    with pytest.raises(AppError, match="Ścieżka|ścieżka|Wynik"):
        guard_cli(args(**options), client)


def test_database_override_blocked(client):
    values = args()
    values.data_dir = client.parent / "other"
    with pytest.raises(AppError):
        guard_cli(values, client)


def test_output_symlink_blocked(client):
    other = client.parent / "other"
    other.mkdir()
    (client / "reports").symlink_to(other, target_is_directory=True)
    with pytest.raises(AppError):
        guard_cli(args(), client)


def test_foreign_configuration_blocked(client):
    path = client / "config/local"
    path.mkdir(parents=True)
    (path / "meta-client-b.json").write_text("{}")
    with pytest.raises(AppError):
        guard_cli(args(), client)


def test_child_directory_cannot_skip_guard(client, monkeypatch, capsys):
    child = client / "reports"
    child.mkdir()
    monkeypatch.chdir(child)
    assert meta_run(["capabilities"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "WORKSPACE_ROOT_REQUIRED"


def test_demo_cannot_contaminate_client(client, capsys):
    assert meta_run(["--demo", "clients", "list"]) == 3
    assert "SCOPE_MISMATCH" in capsys.readouterr().out


def test_context_lifecycle_and_integrity(client, tmp_path):
    source = tmp_path / "meeting.md"
    source.write_text("Potwierdzone ustalenia klienta A.")
    options = argparse.Namespace(
        file=source,
        title="Spotkanie",
        type="dowolny-typ",
        project="jesien",
        tag=["oferta"],
        valid_until="2020-01-01",
    )
    item = add_context(client, options)
    assert item["status"] == "draft"
    assert source.read_text() == (client / item["file"]).read_text()
    assert context_items(client)["items"][0]["expired"] is True
    change = argparse.Namespace(id=item["id"], status="confirmed", reason="Operator potwierdził")
    confirmed = set_context_status(client, change)
    assert confirmed["status"] == "confirmed"
    assert confirmed["history"][0]["previous"] == "draft"
    replacement = add_context(client, options)
    assert replacement["id"] != item["id"]
    (client / item["file"]).write_text("Zmieniony plik")
    assert context_items(client)["items"][0]["integrity"] == "changed_or_missing"
    with pytest.raises(AppError):
        set_context_status(client, change)


def test_contexts_never_cross_clients(client, tmp_path, monkeypatch):
    assert run(["context", "list"]) == 0
    context = client / "context"
    context.mkdir(exist_ok=True)
    (context / "index.json").write_text(
        json.dumps({"schema_version": "1.0", "client_id": "client-b", "items": []})
    )
    with pytest.raises(AppError):
        context_items(client)


def test_context_lock_prevents_lost_update(client):
    with context_lock(client), pytest.raises(AppError):
        with context_lock(client):
            pass


def load_installer():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("workbench_install", root / "install.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_installer_copies_only_allowlist_and_does_not_overwrite(tmp_path):
    installer = load_installer()
    source = Path(__file__).resolve().parents[1]
    target = tmp_path / "separate-client"
    installer.create_workspace(source, target, "example", "Example", "codex")
    assert json.loads((target / "workspace.json").read_text())["client_id"] == "example"
    assert list((target / "secrets").iterdir()) == []
    assert list((target / "reports").iterdir()) == []
    assert list((target / "data").iterdir()) == []
    assert (target / ".gitignore").read_text().endswith("*\n")
    assert (target / ".agents/rules/meta-ads.md").is_file()
    assert not (target / ".git").exists()
    with pytest.raises(ValueError):
        installer.create_workspace(source, target, "other", "Other", "codex")
    assert json.loads((target / "workspace.json").read_text())["client_id"] == "example"


def test_installer_rejects_shared_git_root(tmp_path):
    installer = load_installer()
    source = Path(__file__).resolve().parents[1]
    (tmp_path / ".git").mkdir()
    with pytest.raises(ValueError):
        installer.create_workspace(source, tmp_path / "client", "example", "Example", "codex")


def test_config_content_cannot_change_client(client, capsys):
    path = client / "config/local"
    path.mkdir(parents=True)
    (path / "meta-client-a.json").write_text(json.dumps({"client_id": "client-b"}))
    assert meta_run(["clients", "list"]) == 3
    assert "SCOPE_MISMATCH" in capsys.readouterr().out


def test_wrapper_supports_global_meta_options(client, capsys):
    assert run(["meta", "--output", "output/capabilities.json", "capabilities"]) == 0
    assert (client / "output/capabilities.json").is_file()
    assert json.loads(capsys.readouterr().out)["data"]["writes"] is False
