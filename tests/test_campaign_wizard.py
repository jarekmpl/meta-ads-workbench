import copy
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from pydantic import SecretStr, ValidationError

from meta_ads_manager.campaign_api import CampaignAPI
from meta_ads_manager.campaign_executor import execute, record_approval
from meta_ads_manager.campaign_models import CreationBrief, WizardAnswer, WizardApproval
from meta_ads_manager.campaign_planner import EDITABLE, compile_plan, complete, digest, readiness
from meta_ads_manager.campaign_store import WizardStore
from meta_ads_manager.campaign_website import Extractor, public_target
from meta_ads_manager.cli import run
from meta_ads_manager.decision_store import canonical
from meta_ads_manager.errors import AppError
from meta_ads_manager.meta_connection import Connection, Credentials

SCOPE = {"schema_version": "1.0", "client_id": "client-a", "account_id": "act_123"}


def brief_data(**updates):
    start = (
        (datetime.now(UTC) + timedelta(days=3))
        .replace(microsecond=0)
        .astimezone(ZoneInfo("Europe/Warsaw"))
    )
    return {
        **SCOPE,
        "kind": "creation_brief",
        "project_id": "main",
        "client_code": "Żółć",
        "project_code": "OFERTA",
        "goal_id": "leads",
        "goal_revision": 1,
        "goal_kind": "leads",
        "offer": "Konsultacja testowa",
        "result_definition": "Wysłany formularz",
        "measurement": "lead_form",
        "language": "pl",
        "role": "TEST",
        "currency": "PLN",
        "timezone": "Europe/Warsaw",
        "budget_period": "daily",
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(days=7)).isoformat(),
        "landing_url": "https://example.com/offer",
        "page_id": "201",
        "lead_form_id": "301",
        "special_ad_categories": [],
        "dsa_beneficiary": "Firma testowa",
        "dsa_payor": "Firma testowa",
        "placements": "facebook_feed",
        "followup_process": "Operator kontaktuje się z leadem.",
        "test_hypothesis": "Sprawdzamy argument oferty.",
        "test_success": "Koszt leada do 50 zł.",
        "test_review": "Po siedmiu pełnych dniach.",
        "stop_condition": "Wyczerpanie budżetu testu.",
        "rights_confirmed": True,
        "measurement_confirmed": True,
        "adsets": [
            {
                "audience_code": "BROAD",
                "countries": ["PL"],
                "age_min": 25,
                "age_max": 65,
                "budget": "50.25",
                "ads": [
                    {
                        "concept": "Korzyść",
                        "image_hash": "a" * 32,
                        "message": "Poznaj ofertę konsultacji.",
                        "headline": "Umów konsultację",
                        "cta": "SIGN_UP",
                    }
                ],
            }
        ],
        **updates,
    }


def answer(identifier, revision, fields):
    return WizardAnswer.model_validate_json(
        canonical(
            {
                **SCOPE,
                "kind": "wizard_answer",
                "draft_id": identifier,
                "expected_revision": revision,
                "fields": {
                    k: {
                        "value": v,
                        "state": "confirmed",
                        "source": "operator",
                        "evidence_ref": "synthetic-message",
                    }
                    for k, v in fields.items()
                },
            }
        )
    )


def approve(store, plan, decision="approve"):
    rows = [r for r in store.all() if r["category"] == "approval" and r["id"] == plan["plan_hash"]]
    revision = rows[-1]["revision"] if rows else 0
    return record_approval(
        store,
        plan,
        WizardApproval.model_validate_json(
            canonical(
                {
                    **SCOPE,
                    "kind": "wizard_approval",
                    "plan_hash": plan["plan_hash"],
                    "approval_id": f"decision-{revision + 1}",
                    "expected_revision": revision,
                    "decision": decision,
                    "operator_name": "Operator testowy",
                    "operator_message": "Akceptuję wskazany dokładny plan testowy.",
                    "evidence_ref": "synthetic-approval",
                }
            )
        ),
    )


@pytest.fixture
def store(tmp_path):
    with WizardStore(tmp_path / "wizard.sqlite3", "client-a", "act_123") as store:
        yield store


@pytest.fixture
def ready(store):
    row = store.start("main", "draft-1")
    row = store.answer(
        answer(row["id"], 1, {k: v for k, v in brief_data().items() if k in EDITABLE})
    )
    brief = complete(row["data"])
    keys = store.reserve(row["id"], row["revision"], brief)
    plan = compile_plan(
        brief,
        keys,
        draft_id=row["id"],
        revision=row["revision"],
        api_version="v26.0",
        resources={"verified": "synthetic"},
        goal={},
    )
    store.save_plan(plan)
    return plan


class FakeAPI:
    def __init__(self):
        self.objects = {}
        self.posts = []
        self.fail_after_create = None
        self.mutate = None
        self.preflight_value = {"verified": "synthetic"}

    def preflight(self, brief):
        return self.preflight_value

    def list(self, edge, fields):
        return [dict(v, id=k) for k, (e, v) in self.objects.items() if e == edge]

    def _create(self, edge, params, *, authorization=None):
        identifier = str(1000 + len(self.posts))
        self.posts.append((edge, copy.deepcopy(params)))
        self.objects[identifier] = (edge, copy.deepcopy(params))
        if self.mutate:
            self.mutate()
        if self.fail_after_create == len(self.posts):
            raise AppError("NETWORK_ERROR", "Synthetic uncertain result", 5)
        return identifier

    def read_created(self, identifier, edge, params):
        result = copy.deepcopy(self.objects[identifier][1])
        if edge == "ads":
            result["creative"] = {"id": result["creative"]["creative_id"]}
        return {**result, "id": identifier, "account_id": "123"}


def test_resume_questions_and_dependency_conflicts(store):
    first = store.start("main", "d1")
    assert len(readiness(first["data"])["questions"]) == 3
    row = store.answer(
        answer(
            "d1",
            1,
            {
                "goal_kind": "leads",
                "measurement": "lead_form",
                "lead_form_id": "301",
                "adsets": brief_data()["adsets"],
            },
        )
    )
    assert "goal_kind" not in readiness(row["data"])["missing"]
    row = store.answer(answer("d1", 2, {"measurement": "web_lead"}))
    assert row["data"]["fields"]["lead_form_id"]["state"] == "conflict"
    assert "pixel_id" in readiness(row["data"])["missing"]
    assert "lead_form_id" not in readiness(row["data"])["missing"]
    assert row["data"]["fields"]["adsets"]["state"] == "conflict"
    assert store.get("draft", "d1", 2)["data"]["fields"]["measurement"]["value"] == "lead_form"
    with pytest.raises(AppError):
        store.answer(answer("d1", 2, {"offer": "Stale"}))


def test_discovery_cannot_confirm_business_decisions(store):
    store.start("main", "d1")
    raw = answer("d1", 1, {"rights_confirmed": True}).model_dump(mode="json")
    raw["fields"]["rights_confirmed"]["source"] = "api"
    with pytest.raises(AppError):
        store.answer(WizardAnswer.model_validate_json(canonical(raw)))
    raw["fields"]["rights_confirmed"]["source"] = "website"
    with pytest.raises(ValidationError):
        WizardAnswer.model_validate_json(canonical(raw))


def test_wrong_scope_and_unknown_fields_do_not_write(store):
    store.start("main", "d1")
    raw = answer("d1", 1, {"offer": "Offer"}).model_dump(mode="json")
    raw["client_id"] = "client-b"
    with pytest.raises(AppError):
        store.answer(WizardAnswer.model_validate_json(canonical(raw)))
    with pytest.raises(AppError):
        store.answer(answer("d1", 1, {"access_token": "unaccepted"}))
    assert store.get("draft", "d1")["revision"] == 1


def test_budget_and_stable_names(store, ready):
    assert ready["operations"][0]["params"]["name"].startswith("ZOLC |")
    assert ready["operations"][1]["params"]["daily_budget"] == 5025
    assert ready["budget_summary"]["amount"] == "50.25"
    assert all(op["params"].get("status", "PAUSED") == "PAUSED" for op in ready["operations"])
    row = store.get("draft", "draft-1")
    assert store.reserve("draft-1", row["revision"], complete(row["data"])) == ready["keys"]
    other = store.reserve("other", 1, complete(row["data"]))
    assert other["campaign"] == "C0002" and other["ads"] == ["A0002"]


@pytest.mark.parametrize(
    "measurement,kind,event",
    [
        ("web_lead", "leads", "LEAD"),
        ("purchase", "sales", "PURCHASE"),
        ("registration", "registrations", "COMPLETE_REGISTRATION"),
        ("custom_proxy", "tickets", None),
    ],
)
def test_supported_website_payloads(measurement, kind, event):
    brief = CreationBrief.model_validate_json(
        canonical(
            brief_data(
                measurement=measurement,
                goal_kind=kind,
                lead_form_id=None,
                pixel_id="401",
                custom_conversion_id="501" if measurement == "custom_proxy" else None,
            )
        )
    )
    plan = compile_plan(
        brief,
        {"campaign": "C0001", "adsets": ["S0001"], "ads": ["A0001"]},
        draft_id="d1",
        revision=1,
        api_version="v26.0",
        resources={},
        goal={},
    )
    promoted = plan["operations"][1]["params"]["promoted_object"]
    assert promoted["pixel_id"] == "401"
    assert promoted.get("custom_event_type") == event
    assert plan["operations"][1]["params"]["destination_type"] == "WEBSITE"


@pytest.mark.parametrize(
    "update",
    [
        {"special_ad_categories": ["HOUSING"]},
        {"rights_confirmed": False},
        {"goal_kind": "sales"},
        {"pixel_id": "401"},
        {"start_time": "2026-09-13T10:00:00"},
    ],
)
def test_unsupported_or_inconsistent_brief_is_rejected(update):
    with pytest.raises(ValidationError):
        CreationBrief.model_validate_json(canonical(brief_data(**update)))


def test_no_approval_means_no_network(store, ready, tmp_path):
    factory = MagicMock()
    with pytest.raises(AppError, match="akceptacji"):
        execute(store, ready, factory, tmp_path / "lock")
    factory.assert_not_called()


@pytest.mark.parametrize("change", ["tamper", "expired", "foreign", "edited", "revoked", "delete"])
def test_invalid_plan_blocks_network(store, ready, tmp_path, change):
    approve(store, ready)
    plan = copy.deepcopy(ready)
    if change == "tamper":
        plan["operations"][0]["params"]["name"] = "changed"
    if change == "expired":
        plan["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        plan["plan_hash"] = digest(plan)
    if change == "foreign":
        plan["client_id"] = "other"
        plan["plan_hash"] = digest(plan)
    if change == "edited":
        store.answer(answer("draft-1", 2, {"offer": "New offer"}))
    if change == "revoked":
        approve(store, ready, "revoke")
    if change == "delete":
        plan["operations"][0]["params"]["status"] = "DELETED"
        plan["plan_hash"] = digest(plan)
    factory = MagicMock()
    with pytest.raises(AppError):
        execute(store, plan, factory, tmp_path / "lock")
    factory.assert_not_called()


def test_execution_readback_and_idempotent_retry(store, ready, tmp_path):
    approve(store, ready)
    api = FakeAPI()
    result = execute(store, ready, lambda: api, tmp_path / "lock")
    assert result["status"] == "SUCCEEDED"
    assert len(api.posts) == 4
    assert api.posts[1][1]["campaign_id"] == "1000"
    assert api.posts[3][1]["creative"]["creative_id"] == "1002"
    assert execute(store, ready, lambda: api, tmp_path / "lock") == result
    assert len(api.posts) == 4


def test_lost_response_reconciles_before_resuming(store, ready, tmp_path):
    approve(store, ready)
    api = FakeAPI()
    api.fail_after_create = 2
    with pytest.raises(AppError):
        execute(store, ready, lambda: api, tmp_path / "lock")
    assert len(api.posts) == 2
    state = execute(store, ready, lambda: api, tmp_path / "lock", reconcile_only=True)
    assert state["status"] == "RECONCILED_PARTIAL" and len(api.posts) == 2
    assert execute(store, ready, lambda: api, tmp_path / "lock")["status"] == "SUCCEEDED"
    assert len(api.posts) == 4


def test_unknown_absent_object_never_reposts(store, ready, tmp_path):
    approve(store, ready)
    api = FakeAPI()
    api.fail_after_create = 1
    with pytest.raises(AppError):
        execute(store, ready, lambda: api, tmp_path / "lock")
    api.objects.clear()
    with pytest.raises(AppError, match="jednoznacznie"):
        execute(store, ready, lambda: api, tmp_path / "lock")
    assert len(api.posts) == 1


def test_changed_account_and_changed_readback_stop_writes(store, ready, tmp_path):
    approve(store, ready)
    api = FakeAPI()
    api.preflight_value = {"changed": True}
    with pytest.raises(AppError):
        execute(store, ready, lambda: api, tmp_path / "lock")
    assert not api.posts
    api.preflight_value = ready["resources"]
    api.mutate = lambda: api.objects["1000"][1].update(status="ACTIVE")
    with pytest.raises(AppError):
        execute(store, ready, lambda: api, tmp_path / "lock")
    assert len(api.posts) == 1
    assert store.execution(ready["plan_hash"])["status"] == "UNCERTAIN"


def test_revocation_during_run_stops_next_create(store, ready, tmp_path):
    approve(store, ready)
    api = FakeAPI()
    api.mutate = lambda: approve(store, ready, "revoke")
    with pytest.raises(AppError):
        execute(store, ready, lambda: api, tmp_path / "lock")
    assert len(api.posts) == 1


def transport(mode="approved_create_paused"):
    api = CampaignAPI(
        Connection(
            client_id="client-a", account_id="act_123", api_version="v26.0", access_mode=mode
        ),
        Credentials(app_id="1", access_token=SecretStr("SYNTHETIC")),
    )
    api.opener = MagicMock()
    return api


@pytest.mark.parametrize(
    "edge,params",
    [
        ("123", {"name": "X", "status": "PAUSED"}),
        ("campaigns", {"status": "ACTIVE"}),
        ("campaigns", {"status": "DELETED"}),
        ("campaigns", {"method": "DELETE", "status": "PAUSED"}),
        ("ads", {"batch": [], "status": "PAUSED"}),
    ],
)
def test_transport_rejects_forbidden_writes_before_network(edge, params):
    api = transport()
    with pytest.raises(AppError):
        api._create(edge, params)
    api.opener.open.assert_not_called()


def test_readonly_connection_blocks_create():
    api = transport("read_only")
    with pytest.raises(AppError):
        api._create("campaigns", {"name": "X", "status": "PAUSED"})
    api.opener.open.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://user:pass@example.com",
        "https://example.com:444",
        "https://127.0.0.1",
        "https://[::1]",
    ],
)
def test_website_rejects_unsafe_targets(url):
    with pytest.raises(AppError):
        public_target(url)


def test_dns_private_address_is_rejected(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("10.1.1.1", 443))])
    with pytest.raises(AppError):
        public_target("https://example.com")


def test_website_extracts_data_and_does_not_run_script():
    p = Extractor("https://example.com/offer")
    p.feed(
        '<title>Oferta</title><meta name="description" content="Konsultacje">'
        '<script>secret()</script><p>Opis oferty</p><a href="/details">Szczegóły</a>'
        '<img src="/image.png">'
    )
    assert p.title == ["Oferta"] and "secret()" not in p.text
    assert p.links == ["https://example.com/details"]
    assert p.images == ["https://example.com/image.png"]


def test_cli_resumes_wizard_without_credentials(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config/local").mkdir(parents=True)
    (tmp_path / "config/local/meta-client-a.json").write_text(
        canonical({"client_id": "client-a", "account_id": "act_123", "api_version": "v26.0"})
    )
    scope = ["--client", "client-a", "--account", "act_123"]
    assert run(["wizard", "start", *scope, "--project", "main"]) == 0
    row = json.loads(capsys.readouterr().out)["data"]
    (tmp_path / "answer.json").write_text(
        answer(row["id"], 1, {"goal_kind": "leads", "offer": "Konsultacja"}).model_dump_json()
    )
    assert run(["wizard", "answer", *scope, "--file", "answer.json"]) == 0
    result = json.loads(capsys.readouterr().out)["data"]
    assert "offer" not in result["missing"]
    assert run(["wizard", "show", *scope, "--id", row["id"]]) == 0
    assert json.loads(capsys.readouterr().out)["data"] == result
    assert run(["wizard", "plan", *scope, "--id", row["id"]]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "BRIEF_INCOMPLETE"


def test_full_cli_plan_approval_and_goal_link(tmp_path, monkeypatch, capsys):
    from pathlib import Path

    from meta_ads_manager.decision_models import BusinessGoal
    from meta_ads_manager.decision_store import Decisions

    example = json.loads(
        (Path(__file__).resolve().parents[1] / "examples/business-goal.json").read_text()
    )
    example["goal_id"] = "leads"
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config/local").mkdir(parents=True)
    (tmp_path / "config/local/meta-client-a.json").write_text(
        canonical(
            {
                "client_id": "client-a",
                "account_id": "act_123",
                "api_version": "v26.0",
                "access_mode": "approved_create_paused",
            }
        )
    )
    with Decisions(tmp_path / "data/decisions.sqlite3", "client-a", "act_123") as goals:
        goals.save_goal(BusinessGoal.model_validate_json(canonical(example)))
    fake = FakeAPI()
    monkeypatch.setattr("meta_ads_manager.campaign_cli.load_credentials", lambda *a: None)
    monkeypatch.setattr("meta_ads_manager.campaign_cli.CampaignAPI", lambda *a: fake)
    scope = ["--client", "client-a", "--account", "act_123"]
    assert run(["wizard", "start", *scope, "--project", "main"]) == 0
    draft = json.loads(capsys.readouterr().out)["data"]
    (tmp_path / "input.json").write_text(
        answer(
            draft["id"], 1, {k: v for k, v in brief_data().items() if k in EDITABLE}
        ).model_dump_json()
    )
    assert run(["wizard", "answer", *scope, "--file", "input.json"]) == 0
    capsys.readouterr()
    assert run(["wizard", "plan", *scope, "--id", draft["id"], "--preview", "plan.md"]) == 0
    plan = json.loads(capsys.readouterr().out)["data"]
    assert (tmp_path / "plan.md").read_text().count("Przed: obiekt nie istnieje.") == 4
    assert not fake.posts
    assert run(["wizard", "execute", *scope, "--plan-hash", plan["plan_hash"]]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "APPROVAL_REQUIRED"
    approval = {
        **SCOPE,
        "kind": "wizard_approval",
        "plan_hash": plan["plan_hash"],
        "decision": "approve",
        "operator_name": "Operator testowy",
        "approval_id": "decision-1",
        "expected_revision": 0,
        "operator_message": "Akceptuję dokładny plan syntetyczny.",
        "evidence_ref": "synthetic-message",
    }
    (tmp_path / "approval.json").write_text(canonical(approval))
    assert run(["wizard", "approve", *scope, "--file", "approval.json"]) == 0
    capsys.readouterr()
    assert run(["wizard", "execute", *scope, "--plan-hash", plan["plan_hash"]]) == 0
    result = json.loads(capsys.readouterr().out)["data"]
    assert result["status"] == "SUCCEEDED"
    assert result["goal_assignment"]["data"]["campaign_id"] == "1000"
    assert result["goal_assignment"]["data"]["goal_id"] == "leads"
    assert run(["wizard", "execute", *scope, "--plan-hash", plan["plan_hash"]]) == 0
    capsys.readouterr()
    assert len(fake.posts) == 4


def test_discovery_fills_only_technical_fields(store):
    row = store.start("main", "d1")
    result = store.evidence(
        "d1",
        row["revision"],
        "resource_evidence",
        {"account": {"currency": "PLN", "timezone_name": "Europe/Warsaw"}},
    )
    assert result["data"]["fields"]["currency"]["state"] == "confirmed"
    assert "rights_confirmed" not in result["data"]["fields"]
    assert "currency" not in readiness(result["data"])["missing"]


def test_read_transport_never_follows_paging_urls_or_foreign_pages():
    api = transport()
    api._request = MagicMock(
        side_effect=[
            {
                "data": [{"id": "201"}],
                "paging": {
                    "next": "https://elsewhere/?access_token=secret",
                    "cursors": {"after": "next-page"},
                },
            },
            {"data": [{"id": "202"}]},
        ]
    )
    assert len(api.list("promote_pages", "id")) == 2
    assert api._request.call_args_list[1].args[0] == "act_123/promote_pages"
    assert api._request.call_args_list[1].args[1]["after"] == "next-page"
    with pytest.raises(AppError):
        api.list("leadgen_forms", "id", page_id="999")


def test_preflight_rejects_missing_image_and_foreign_account():
    api = transport()
    brief = CreationBrief.model_validate_json(canonical(brief_data()))
    api._request = MagicMock(return_value={"id": "act_999"})
    with pytest.raises(AppError):
        api.preflight(brief)
    api.account_state = lambda: {
        "id": "act_123",
        "currency": "PLN",
        "timezone_name": "Europe/Warsaw",
        "account_status": 1,
    }
    api.list = lambda edge, fields, **kw: [{"id": "201"}] if edge == "promote_pages" else []
    with pytest.raises(AppError):
        api.preflight(brief)
    api.opener.open.assert_not_called()


def test_retry_cannot_restore_revoked_approval(store, ready, tmp_path):
    original = approve(store, ready)
    approve(store, ready, "revoke")
    result = record_approval(
        store, ready, WizardApproval.model_validate_json(canonical(original["data"]))
    )
    assert result["data"]["decision"] == "revoke"
    factory = MagicMock()
    with pytest.raises(AppError):
        execute(store, ready, factory, tmp_path / "lock")
    factory.assert_not_called()


def test_stale_new_approval_cannot_overwrite_revocation(store, ready):
    original = approve(store, ready)
    approve(store, ready, "revoke")
    raw = original["data"]
    raw["approval_id"] = "another"
    with pytest.raises(AppError):
        record_approval(store, ready, WizardApproval.model_validate_json(canonical(raw)))


def test_post_body_keeps_credentials_out_of_url(store, ready):
    import io
    from urllib.parse import parse_qs

    api = transport()
    api.opener.open.return_value.__enter__.return_value = io.StringIO('{"id":"901"}')
    from meta_ads_manager.campaign_executor import CreationAuthorization

    approve(store, ready)
    op = ready["operations"][0]
    store.receipt(
        ready["plan_hash"],
        {"status": "RUNNING", "operations": {op["key"]: {"status": "SENDING", "id": None}}},
    )
    authorization = CreationAuthorization(store, ready, op["key"])
    assert api._create("campaigns", op["params"], authorization=authorization) == "901"
    with pytest.raises(AppError):
        api._create("campaigns", op["params"], authorization=authorization)
    assert api.opener.open.call_count == 1
    request = api.opener.open.call_args.args[0]
    assert request.get_method() == "POST"
    assert request.full_url == "https://graph.facebook.com/v26.0/act_123/campaigns"
    assert parse_qs(request.data.decode())["status"] == ["PAUSED"]
    assert "SYNTHETIC" not in request.full_url and "SYNTHETIC" not in request.data.decode()


@pytest.mark.parametrize("lose_response", [False, True])
def test_executor_through_guarded_transport(store, ready, tmp_path, lose_response):
    import io
    from urllib.error import URLError
    from urllib.parse import parse_qs, urlsplit

    approve(store, ready)
    api = transport()
    api.preflight = lambda _: ready["resources"]
    objects = {}
    posts = []
    api.list = lambda edge, fields: [dict(v, id=k) for k, (e, v) in objects.items() if e == edge]

    def send(request, timeout):
        key = urlsplit(request.full_url).path.split("/")[-1]
        if request.get_method() == "POST":
            params = {}
            for name, values in parse_qs(request.data.decode()).items():
                value = values[0]
                if value.startswith(("{", "[")) or value in ("true", "false"):
                    value = json.loads(value)
                params[name] = value
            identifier = str(2000 + len(posts))
            posts.append(key)
            objects[identifier] = (key, params)
            if lose_response and len(posts) == 2:
                raise URLError("synthetic dropped response")
            result = {"id": identifier}
        else:
            edge, params = objects[key]
            result = copy.deepcopy(params)
            result.update(id=key, account_id="123")
            if edge == "ads":
                result["creative"] = {"id": result["creative"]["creative_id"]}
        response = MagicMock()
        response.__enter__.return_value = io.StringIO(json.dumps(result))
        return response

    api.opener.open.side_effect = send
    if lose_response:
        with pytest.raises(AppError):
            execute(store, ready, lambda: api, tmp_path / "lock")
        assert len(posts) == 2
    result = execute(store, ready, lambda: api, tmp_path / "lock")
    assert result["status"] == "SUCCEEDED" and len(posts) == 4
    assert result["ids"]["C0001"] == "2000"


@pytest.mark.parametrize("method", ["DELETE", "PATCH", "PUT"])
def test_lowest_transport_has_no_arbitrary_write_method(method):
    api = transport()
    with pytest.raises(AppError):
        api._request("act_123/campaigns", {}, method=method)
    api.opener.open.assert_not_called()


def test_lowest_transport_rejects_post_without_authorization():
    api = transport()
    with pytest.raises(AppError):
        api._request("act_123/campaigns", {"name": "X", "status": "PAUSED"}, method="POST")
    api.opener.open.assert_not_called()
