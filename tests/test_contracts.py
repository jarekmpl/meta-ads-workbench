import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from meta_ads_manager.cli import SUPPORTED_CONTRACTS as CONTRACTS
from meta_ads_manager.models import ClientProfile, DemoDataset, Fact, Snapshot
from meta_ads_manager.provider import DemoProvider

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("path", sorted((ROOT / "examples").glob("*.json")))
def test_existing_examples_are_valid_contracts(path):
    raw = path.read_text()
    data = json.loads(raw)
    model = CONTRACTS[data["kind"]]
    model.model_validate_json(raw)
    jsonschema.validate(data, model.model_json_schema())


@pytest.mark.parametrize("bad", [12.1, 12, True, "NaN", "Infinity", "-1", "abc"])
def test_decimal_values_reject_coercion_and_invalid_values(bad):
    fact = {
        "campaign_id": "campaign",
        "day": "2026-09-01",
        "spend": bad,
        "impressions": 100,
        "link_clicks": 2,
        "conversions": "1",
        "conversion_value": None,
    }
    with pytest.raises(ValidationError):
        Fact.model_validate_json(json.dumps(fact))


def test_profile_rejects_unknown_fields_and_invalid_project_references():
    data = DemoProvider().dataset.profiles[0].model_dump(mode="json")
    data["access_token"] = "DO_NOT_PRINT_THIS_SECRET"
    with pytest.raises(ValidationError):
        ClientProfile.model_validate_json(json.dumps(data))
    del data["access_token"]
    data["projects"][0]["account_ids"] = ["foreign_account"]
    with pytest.raises(ValidationError):
        ClientProfile.model_validate_json(json.dumps(data))


@pytest.mark.parametrize(
    "mutation", ["missing", "duplicate", "foreign", "partial", "today", "timezone"]
)
def test_snapshot_requires_complete_unique_scoped_days(mutation):
    data = DemoProvider().dataset.snapshots[0].model_dump(mode="json")
    if mutation == "missing":
        data["facts"].pop()
    elif mutation == "duplicate":
        data["facts"].append(data["facts"][0])
    elif mutation == "foreign":
        data["facts"][0]["campaign_id"] = "foreign_campaign"
    elif mutation == "partial":
        data["complete"] = False
    elif mutation == "timezone":
        data["spec"]["timezone"] = "Invalid/Timezone"
    else:
        data["fetched_at"] = "2026-09-08T08:00:00Z"
    with pytest.raises(ValidationError):
        Snapshot.model_validate_json(json.dumps(data))


def test_dataset_rejects_shared_account_ownership():
    data = DemoProvider().dataset.model_dump(mode="json")
    data["profiles"][1]["accounts"][0]["account_id"] = "act_DEMO_LEADS"
    data["profiles"][1]["projects"][0]["account_ids"] = ["act_DEMO_LEADS"]
    with pytest.raises(ValidationError):
        DemoDataset.model_validate_json(json.dumps(data))


def test_fractional_conversions_and_unknown_values_are_preserved():
    raw = {
        "campaign_id": "c1",
        "day": "2026-09-01",
        "spend": "12.30",
        "impressions": 100,
        "link_clicks": 2,
        "conversions": "0.5",
        "conversion_value": None,
    }
    fact = Fact.model_validate_json(json.dumps(raw))
    assert fact.model_dump(mode="json")["conversions"] == "0.5"
    assert fact.conversion_value is None


def test_snapshot_rejects_conflicting_goal_binding():
    data = DemoProvider().dataset.model_dump(mode="json")
    data["snapshots"][0]["campaigns"][0]["goal_id"] = "commerce-pl"
    with pytest.raises(ValidationError):
        DemoDataset.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("kind", CONTRACTS)
def test_committed_schemas_match_models(kind):
    saved = json.loads((ROOT / "schemas" / f"{kind}.schema.json").read_text())
    assert saved == CONTRACTS[kind].model_json_schema()
