from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from meta_ads_manager.cli import run
from meta_ads_manager.creative_review import CreativeAPI
from meta_ads_manager.errors import AppError
from meta_ads_manager.meta_connection import Connection, Credentials, MetaReadClient


@pytest.mark.parametrize("client_type", [MetaReadClient, CreativeAPI])
@pytest.mark.parametrize("params", [
    {"method": "DELETE"},
    {"method": "POST", "status": "DELETED"},
    {"_method": "POST", "daily_budget": "10000"},
    {"METHOD": "DELETE"},
    {"http_method": "DELETE"},
    {"X-HTTP-Method-Override": "POST"},
    {"batch": '[{"method":"DELETE","relative_url":"123"}]'},
])
def test_write_override_is_blocked_before_network(client_type, params):
    client = client_type(
        Connection(client_id="test", account_id="act_1", api_version="v26.0"),
        Credentials(app_id="1", access_token=SecretStr("FAKE_TOKEN")),
    )
    client.opener = MagicMock()
    edge = "account" if client_type is MetaReadClient else "act_1"
    with pytest.raises(AppError) as error:
        client.get(edge, params)
    assert error.value.code == "READ_ONLY_VIOLATION"
    client.opener.open.assert_not_called()


def test_capabilities_discloses_account_rules(capsys):
    import json

    assert run(["capabilities"]) == 0
    data = json.loads(capsys.readouterr().out)["data"]
    assert data["writes"] is False
    policy = data["account_change_policy"]
    assert policy["deletion_allowed"] is False
    assert policy["user_approval_required_for_every_change"] is True
    assert policy["autonomous_writes_allowed"] is False
    assert policy["write_executor_implemented"] is False
