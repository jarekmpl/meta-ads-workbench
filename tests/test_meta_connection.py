import io
import json
import os
from unittest.mock import MagicMock
from urllib.error import HTTPError

import pytest
from pydantic import SecretStr

from meta_ads_manager.cli import run
from meta_ads_manager.errors import AppError
from meta_ads_manager.meta_connection import (
    Connection,
    Credentials,
    MetaReadClient,
    NoRedirect,
    check_connection,
    config_path,
    connection_status,
    load_credentials,
    save_private,
    secret_path,
    store_credentials,
)


def configured(tmp_path):
    connection = Connection(
        client_id="firma", app_id="123", account_id="act_456", api_version="v99.0"
    )
    save_private(config_path(tmp_path, "firma"), connection.model_dump(mode="json"))
    save_private(
        secret_path(tmp_path, "firma"),
        {"app_id": "123", "access_token": "FAKE_SECRET", "app_secret": None},
    )
    return connection


def test_incomplete_init_is_not_verified_and_preserves_existing_config(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    assert run(["auth", "init", "--client", "firma"]) == 0
    result = json.loads(capsys.readouterr().out)["data"]
    assert result["status"] == "INCOMPLETE" and not result["access_verified"]
    assert set(result["missing_requirements"]) == {
        "app_id",
        "account_id",
        "api_version",
        "credentials",
    }
    assert run(["auth", "init", "--client", "firma"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "CONFIG_EXISTS"


def test_secrets_are_scoped_and_not_read_by_status(tmp_path):
    connection = configured(tmp_path)
    status = connection_status(tmp_path, "firma")
    assert status["status"] == "READY_FOR_CHECK" and not status["access_verified"]
    assert "FAKE_SECRET" not in json.dumps(status)
    assert secret_path(tmp_path, "firma").stat().st_mode & 0o777 == 0o600
    assert "FAKE_SECRET" not in repr(load_credentials(tmp_path, connection))
    connection.app_id = "999"
    with pytest.raises(AppError, match="innej"):
        load_credentials(tmp_path, connection)


def test_secret_file_with_broad_access_is_rejected(tmp_path):
    connection = configured(tmp_path)
    os.chmod(secret_path(tmp_path, "firma"), 0o644)
    with pytest.raises(AppError, match="600"):
        load_credentials(tmp_path, connection)


def test_store_token_refuses_piped_input_and_unsafe_client_path(tmp_path, monkeypatch):
    connection = Connection(client_id="firma", app_id="123")
    save_private(config_path(tmp_path, "firma"), connection.model_dump(mode="json"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(AppError, match="interaktywnym"):
        store_credentials(tmp_path, "firma")
    with pytest.raises(AppError):
        config_path(tmp_path, "../other")
    assert not secret_path(tmp_path, "firma").exists()


def test_request_is_read_only_and_token_is_not_in_url():
    client = MetaReadClient(
        Connection(client_id="firma", app_id="123", account_id="act_456", api_version="v99.0"),
        Credentials(app_id="123", access_token=SecretStr("FAKE_SECRET")),
    )
    response = MagicMock()
    response.__enter__.return_value = io.BytesIO(b'{"id":"act_456"}')
    client.opener = MagicMock()
    client.opener.open.return_value = response
    assert client.get("account")["id"] == "act_456"
    request = client.opener.open.call_args.args[0]
    assert request.method == "GET"
    assert request.full_url.startswith("https://graph.facebook.com/v99.0/act_456?")
    assert "FAKE_SECRET" not in request.full_url
    assert request.get_header("Authorization") == "Bearer FAKE_SECRET"
    with pytest.raises(AppError):
        client.get("https://untrusted.example")


def test_api_errors_and_redirects_do_not_leak_credentials():
    client = MetaReadClient(
        Connection(client_id="firma", app_id="123", account_id="act_456", api_version="v99.0"),
        Credentials(app_id="123", access_token=SecretStr("FAKE_SECRET")),
    )
    client.opener = MagicMock()
    client.opener.open.side_effect = HTTPError(
        "https://graph.facebook.com",
        400,
        "FAKE_SECRET",
        {},
        io.BytesIO(b'{"error":{"code":190,"message":"FAKE_SECRET"}}'),
    )
    with pytest.raises(AppError) as error:
        client.get("account")
    assert error.value.code == "AUTH_REQUIRED"
    assert "FAKE_SECRET" not in str(error.value)
    with pytest.raises(AppError):
        NoRedirect().redirect_request(None, None, 302, "", {}, "https://untrusted.example")


def test_access_check_verifies_both_account_and_insights(tmp_path, monkeypatch):
    configured(tmp_path)
    get = MagicMock(side_effect=[{"id": "act_456", "name": "Account"}, {"data": []}])
    monkeypatch.setattr(MetaReadClient, "get", get)
    result = check_connection(tmp_path, "firma")
    assert get.call_count == 2
    assert result["status"] == "VERIFIED"
    assert result["reporting_implemented"] and not result["writes"]
    assert not result["token_expiry_checked"]
    assert "FAKE_SECRET" not in json.dumps(result)


def test_wrong_account_is_rejected_before_insights(tmp_path, monkeypatch):
    configured(tmp_path)
    get = MagicMock(return_value={"id": "act_999"})
    monkeypatch.setattr(MetaReadClient, "get", get)
    with pytest.raises(AppError, match="innego"):
        check_connection(tmp_path, "firma")
    assert get.call_count == 1
