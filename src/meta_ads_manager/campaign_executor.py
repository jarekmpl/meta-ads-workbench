"""Only approved immutable plans; durable send intent, readback and conservative recovery."""

import fcntl
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from meta_ads_manager.campaign_models import CreationBrief
from meta_ads_manager.campaign_planner import digest, resolve
from meta_ads_manager.decision_store import canonical, fail
from meta_ads_manager.errors import AppError


@dataclass(frozen=True)
class CreationAuthorization:
    store: object
    plan: dict
    key: str


def authorize_request(authorization, connection, edge, params):
    if not isinstance(authorization, CreationAuthorization):
        fail("APPROVAL_REQUIRED", "Żądanie nie pochodzi z zatwierdzonego wykonania planu.")
    with authorization.store.db:
        authorization.store.db.execute("BEGIN IMMEDIATE")
        store, plan = authorization.store, authorization.plan
        require_approval(store, plan)
        if (connection.client_id, connection.account_id) != (plan["client_id"], plan["account_id"]):
            fail("SCOPE_MISMATCH", "Połączenie należy do innego klienta lub konta.")
        if store.get("plan", plan["plan_hash"])["data"] != plan:
            fail("PLAN_CHANGED", "Żądanie nie odpowiada zapisanemu planowi.")
        state = store.execution(plan["plan_hash"])
        pending = state["operations"].get(authorization.key, {})
        if state["status"] != "RUNNING" or pending.get("status") != "SENDING":
            fail("EXECUTION_STATE", "Operacja nie oczekuje na pierwsze wysłanie.")
        ids = {k: v["id"] for k, v in state["operations"].items() if v["status"] == "VERIFIED"}
        operations = [op for op in plan["operations"] if op["key"] == authorization.key]
        if (
            len(operations) != 1
            or operations[0]["edge"] != edge
            or resolve(operations[0]["params"], ids) != params
        ):
            fail("PLAN_CHANGED", "Parametry żądania różnią się od zatwierdzonej operacji.")
        pending["status"] = "IN_FLIGHT"
        row = store.get("execution", plan["plan_hash"])
        store._append("execution", plan["plan_hash"], row["revision"], state)


def validate_plan(store, plan):
    if digest(plan) != plan["plan_hash"]:
        fail("PLAN_CHANGED", "Treść planu nie zgadza się z jego skrótem.")
    if (plan["client_id"], plan["account_id"]) != (store.client, store.account):
        fail("SCOPE_MISMATCH", "Plan dotyczy innego klienta lub konta.")
    if store.get("draft", plan["draft_id"])["revision"] != plan["draft_revision"]:
        fail("PLAN_CHANGED", "Brief zmienił się po przygotowaniu planu.")
    if datetime.fromisoformat(plan["expires_at"]) <= datetime.now(UTC):
        fail("PLAN_EXPIRED", "Plan wygasł; przygotuj aktualny plan do akceptacji.")
    if plan["policy_version"] != "2026-09-10":
        fail("WRITE_POLICY", "Nieobsługiwana wersja zasad zmian.")
    for op in plan["operations"]:
        if op["edge"] not in ("campaigns", "adsets", "adcreatives", "ads"):
            fail("WRITE_POLICY", "Niedozwolona operacja planu.")
        if op["edge"] != "adcreatives" and op["params"].get("status") != "PAUSED":
            fail("WRITE_POLICY", "Plan musi tworzyć obiekty PAUSED.")


def require_approval(store, plan):
    validate_plan(store, plan)
    rows = [r for r in store.all() if r["category"] == "approval" and r["id"] == plan["plan_hash"]]
    if not rows or rows[-1]["data"]["decision"] != "approve":
        fail("APPROVAL_REQUIRED", "Brak ważnej akceptacji użytkownika dla tego planu.")


def record_approval(store, plan, approval):
    store.scope(approval)
    if approval.plan_hash != plan["plan_hash"]:
        fail("PLAN_CHANGED", "Akceptacja dotyczy innego planu.")
    if approval.decision == "approve":
        validate_plan(store, plan)
    with store.db:
        store.db.execute("BEGIN IMMEDIATE")
        rows = [
            r for r in store.all() if r["category"] == "approval" and r["id"] == plan["plan_hash"]
        ]
        raw = approval.model_dump(mode="json")
        for previous in rows:
            if previous["data"]["approval_id"] == approval.approval_id:
                if previous["data"] != raw:
                    fail("ID_CONFLICT", "ID decyzji wskazuje inną treść.")
                return rows[-1]
        return store._append(
            "approval",
            plan["plan_hash"],
            approval.expected_revision,
            raw,
        )


def matches(expected, actual):
    """Compare supplied settings while allowing unrelated defaults returned by Meta."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(k in actual and matches(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and sorted(map(canonical, expected)) == sorted(
            map(canonical, actual)
        )
    if isinstance(expected, bool):
        return actual in (expected, int(expected), str(int(expected)))
    if isinstance(expected, int):
        return str(expected) == str(actual)
    if isinstance(expected, str) and "T" in expected:
        try:
            return datetime.fromisoformat(expected) == datetime.fromisoformat(actual)
        except (ValueError, TypeError):
            pass
    return expected == actual


def verify(api, plan, op, identifier, params):
    row = api.read_created(identifier, op["edge"], params)
    if row.get("id") != identifier or str(row.get("account_id")) != plan["account_id"].removeprefix(
        "act_"
    ):
        fail("STATE_CONFLICT", "Obiekt należy do innego konta.")
    normalized = dict(row)
    if op["edge"] == "ads" and isinstance(row.get("creative"), dict):
        normalized["creative"] = {"creative_id": row["creative"].get("id")}
    if not matches(params, normalized):
        fail("STATE_CONFLICT", "Odczytane ustawienia różnią się od zaakceptowanego planu.")
    return row


@contextmanager
def execution_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fail("EXECUTION_BUSY", "Inny proces wykonuje plan tego konta.")
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def execute(store, plan, api_factory, lock_path: Path, *, reconcile_only=False):
    # Check before constructing the authenticated network client.
    if not reconcile_only:
        require_approval(store, plan)
    elif (plan["client_id"], plan["account_id"]) != (store.client, store.account):
        fail("SCOPE_MISMATCH", "Obcy plan.")
    with execution_lock(lock_path):
        state = store.execution(plan["plan_hash"])
        if state["status"] == "SUCCEEDED":
            return state
        api = api_factory()
        brief = CreationBrief.model_validate_json(canonical(plan["brief"]))
        if not reconcile_only and api.preflight(brief) != plan["resources"]:
            fail("STATE_CONFLICT", "Zasoby lub stan konta zmieniły się po akceptacji.")
        ids = {}
        for op in plan["operations"]:
            previous = state["operations"].get(op["key"])
            params = resolve(op["params"], ids)
            if previous:
                identifier = previous.get("id")
                if not identifier:
                    candidates = [
                        r
                        for r in api.list(op["edge"], "id,name")
                        if r.get("name") == params["name"]
                    ]
                    if len(candidates) != 1:
                        state["status"] = "UNCERTAIN"
                        store.receipt(plan["plan_hash"], state)
                        fail(
                            "RECONCILIATION_REQUIRED",
                            "Nie można jednoznacznie ustalić wyniku "
                            "zapisu. Zachowano postęp; ponowne tworzenie "
                            "jest zablokowane.",
                        )
                    identifier = candidates[0]["id"]
                try:
                    verified = verify(api, plan, op, identifier, params)
                except AppError:
                    state["status"] = "UNCERTAIN"
                    store.receipt(plan["plan_hash"], state)
                    raise
                previous.update(id=identifier, status="VERIFIED", readback=verified)
                ids[op["key"]] = identifier
                store.receipt(plan["plan_hash"], state)
                continue
            if reconcile_only:
                break
            require_approval(store, plan)
            # New name must not already exist, even when created outside this process.
            if any(r.get("name") == params["name"] for r in api.list(op["edge"], "id,name")):
                fail("NAME_CONFLICT", "Nazwa już istnieje na koncie; przygotuj nowy plan.")
            if api.preflight(brief) != plan["resources"]:
                fail("STATE_CONFLICT", "Stan konta lub zasobów zmienił się przed zapisem.")
            require_approval(store, plan)
            state["status"] = "RUNNING"
            state["operations"][op["key"]] = {"status": "SENDING", "id": None, "params": params}
            store.receipt(plan["plan_hash"], state)
            try:
                # A changed/revoked approval is checked again immediately before POST.
                require_approval(store, plan)
                identifier = api._create(
                    op["edge"],
                    params,
                    authorization=CreationAuthorization(store, plan, op["key"]),
                )
                state["operations"][op["key"]].update(id=identifier, status="CREATED")
                store.receipt(plan["plan_hash"], state)
                verified = verify(api, plan, op, identifier, params)
                state["operations"][op["key"]].update(status="VERIFIED", readback=verified)
                ids[op["key"]] = identifier
                store.receipt(plan["plan_hash"], state)
            except Exception as exc:
                state["status"] = "UNCERTAIN"
                state["error"] = (
                    exc.as_dict() if isinstance(exc, AppError) else {"code": "INTERNAL_ERROR"}
                )
                store.receipt(plan["plan_hash"], state)
                raise
        state["status"] = (
            "SUCCEEDED" if len(ids) == len(plan["operations"]) else "RECONCILED_PARTIAL"
        )
        state["plan_hash"] = plan["plan_hash"]
        state["ids"] = ids
        store.receipt(plan["plan_hash"], state)
        return state
