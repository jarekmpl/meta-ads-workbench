"""First-account onboarding and read-only connectivity checks; no campaign writes."""

import getpass
import hashlib
import hmac
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Annotated, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import Field, SecretStr

from meta_ads_manager.account_policy import validate_read_params
from meta_ads_manager.errors import AppError
from meta_ads_manager.models import Model

ClientId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")]
MetaId = Annotated[str, Field(pattern=r"^[0-9]+$")]


class Connection(Model):
    schema_version: Literal["1.0"] = "1.0"
    client_id: ClientId
    app_id: MetaId | None = None
    business_id: MetaId | None = None
    account_id: Annotated[str, Field(pattern=r"^act_[0-9]+$")] | None = None
    api_version: Annotated[str, Field(pattern=r"^v[0-9]+\.[0-9]+$")] | None = None
    access_mode: Literal["read_only", "approved_create_paused"] = "read_only"


class Credentials(Model):
    app_id: MetaId
    access_token: SecretStr
    app_secret: SecretStr | None = None


def validate_client_id(client: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", client):
        raise AppError("VALIDATION_ERROR", "Niepoprawny identyfikator klienta.", 2)


def config_path(root: Path, client: str) -> Path:
    validate_client_id(client)
    return root / "config" / "local" / f"meta-{client}.json"


def secret_path(root: Path, client: str) -> Path:
    validate_client_id(client)
    return root / "secrets" / f"meta-{client}.json"


def save_private(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # No replacement or symlink traversal: changing an existing configuration is explicit.
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise AppError("CONFIG_EXISTS", "Plik już istnieje; nie został nadpisany.", 2) from exc
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def load_connection(root: Path, client: str) -> Connection:
    path = config_path(root, client)
    if not path.is_file():
        raise AppError("CONFIG_REQUIRED", "Brak konfiguracji klienta; użyj auth init.", 3)
    connection = Connection.model_validate_json(path.read_text())
    if connection.client_id != client:
        raise AppError("SCOPE_MISMATCH", "Konfiguracja należy do innego klienta.", 3)
    return connection


def connection_status(root: Path, client: str) -> dict:
    connection = load_connection(root, client)
    required = ("app_id", "account_id", "api_version")
    missing = [field for field in required if getattr(connection, field) is None]
    credential_exists = secret_path(root, client).is_file()
    if not credential_exists:
        missing.append("credentials")
    return {
        "client_id": client,
        "configuration": connection.model_dump(mode="json"),
        "credentials_present": credential_exists,
        "missing_requirements": missing,
        "status": "INCOMPLETE" if missing else "READY_FOR_CHECK",
        "access_verified": False,
    }


def store_credentials(root: Path, client: str, *, with_app_secret: bool = False) -> dict:
    connection = load_connection(root, client)
    if connection.app_id is None:
        raise AppError("CONFIG_REQUIRED", "Najpierw wpisz ID aplikacji do konfiguracji.", 3)
    if not sys.stdin.isatty():
        raise AppError("INTERACTIVE_REQUIRED", "Token wpisz w lokalnym interaktywnym terminalu.", 2)
    if secret_path(root, client).exists():
        raise AppError("CONFIG_EXISTS", "Poświadczenia już istnieją; nie zostały nadpisane.", 2)
    token = getpass.getpass("Token Meta (ukryty): ").strip()
    app_secret = getpass.getpass("App Secret (ukryty): ").strip() if with_app_secret else None
    if not token or any(char.isspace() for char in token):
        raise AppError("VALIDATION_ERROR", "Token jest pusty lub zawiera białe znaki.", 2)
    if with_app_secret and (not app_secret or not re.fullmatch(r"[a-fA-F0-9]+", app_secret)):
        raise AppError("VALIDATION_ERROR", "Niepoprawny App Secret.", 2)
    credentials = Credentials(
        app_id=connection.app_id,
        access_token=SecretStr(token),
        app_secret=SecretStr(app_secret) if app_secret else None,
    )
    save_private(
        secret_path(root, client),
        {
            "app_id": credentials.app_id,
            "access_token": token,
            "app_secret": app_secret,
        },
    )
    return {"client_id": client, "stored": True, "access_verified": False}


def load_credentials(root: Path, connection: Connection) -> Credentials:
    path = secret_path(root, connection.client_id)
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise AppError("AUTH_REQUIRED", "Brak tokena; użyj auth store-token lokalnie.", 3) from exc
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise AppError("SECRET_PERMISSIONS", "Plik poświadczeń wymaga uprawnień 600.", 3)
    credentials = Credentials.model_validate_json(path.read_text())
    if credentials.app_id != connection.app_id:
        raise AppError(
            "SCOPE_MISMATCH", "Poświadczenia pochodzą z innej konfiguracji aplikacji.", 3
        )
    return credentials


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AppError("API_REDIRECT", "Nieoczekiwane przekierowanie API zostało zablokowane.", 5)


def api_error(payload: dict) -> AppError:
    error = payload.get("error", {})
    code = error.get("code") if isinstance(error, dict) else None
    if code == 190:
        return AppError("AUTH_REQUIRED", "Token jest nieważny lub wygasł.", 3)
    if code in (10, 200):
        return AppError(
            "PERMISSION_DENIED", "Meta odmówiła dostępu; sprawdź przydział i uprawnienia.", 3
        )
    if code in (4, 17, 32, 613, 80000, 80004):
        return AppError(
            "RATE_LIMITED", "Osiągnięto limit API; ponów sprawdzenie później.", 5, retryable=True
        )
    if code == 100:
        # Return only known parameter names, never echo an arbitrary server message.
        message = error.get("message", "")
        fields = [
            field
            for field in (
                "filtering",
                "effective_status",
                "account_currency",
                "time_range",
                "action_values",
                "inline_link_clicks",
                "action_attribution_windows",
            )
            if isinstance(message, str) and field in message
        ]
        detail = ", ".join(fields) or "nierozpoznany parametr"
        return AppError("API_PARAMETER", f"Meta odrzuciła parametry zapytania (100): {detail}.", 5)
    return AppError(
        "API_ERROR", "Meta zwróciła błąd; sprawdź wersję API i konfigurację dostępu.", 5
    )


class MetaReadClient:
    def __init__(self, connection: Connection, credentials: Credentials):
        self.connection = connection
        self.credentials = credentials
        self.opener = build_opener(NoRedirect())

    def get(
        self, edge: Literal["account", "insights", "campaigns"], params: dict | None = None
    ) -> dict:
        if edge not in ("account", "insights", "campaigns"):
            raise AppError("UNSUPPORTED_OPERATION", "Ten endpoint nie jest obsługiwany.", 2)
        account = self.connection.account_id
        version = self.connection.api_version
        if not account or not version:
            raise AppError("CONFIG_REQUIRED", "Brak ID konta lub wersji API.", 3)
        path = account if edge == "account" else f"{account}/{edge}"
        if params is None:
            params = {
                "fields": "spend,impressions",
                "date_preset": "yesterday",
                "level": "account",
                "limit": "1",
            }
            if edge == "account":
                params = {"fields": "id,name,account_id,currency,timezone_name,account_status"}
            elif edge == "campaigns":
                params = {"fields": "id,account_id,name,status,objective", "limit": "100"}
        params = dict(params)
        validate_read_params(params)
        if "access_token" in params:
            raise AppError("VALIDATION_ERROR", "Token nie może być parametrem URL.", 2)
        token = self.credentials.access_token.get_secret_value()
        if self.credentials.app_secret:
            params["appsecret_proof"] = hmac.new(
                self.credentials.app_secret.get_secret_value().encode(),
                token.encode(),
                hashlib.sha256,
            ).hexdigest()
        request = Request(
            f"https://graph.facebook.com/{version}/{path}?{urlencode(params)}",
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        try:
            with self.opener.open(request, timeout=20) as response:
                payload = json.load(response)
        except HTTPError as exc:
            try:
                payload = json.loads(exc.read())
            except (ValueError, OSError):
                payload = {}
            raise api_error(payload if isinstance(payload, dict) else {}) from None
        except (URLError, TimeoutError, OSError):
            raise AppError(
                "NETWORK_ERROR", "Nie udało się połączyć z API Meta.", 5, retryable=True
            ) from None
        except ValueError:
            raise AppError("API_RESPONSE", "Niepoprawny format odpowiedzi API.", 5) from None
        if not isinstance(payload, dict):
            raise AppError("API_RESPONSE", "Niepoprawny format odpowiedzi API.", 5)
        if "error" in payload:
            raise api_error(payload)
        return payload

    def pages(self, edge: Literal["insights", "campaigns"], params: dict) -> list[dict]:
        """Use only cursors, never follow Meta paging URLs (which can contain tokens)."""
        result = []
        seen = set()
        query = dict(params)
        for _ in range(1000):
            payload = self.get(edge, query)
            rows = payload.get("data")
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise AppError("API_RESPONSE", "Niepoprawna lista danych API.", 5)
            result.extend(rows)
            paging = payload.get("paging", {})
            if not isinstance(paging, dict):
                raise AppError("API_RESPONSE", "Niepoprawna paginacja API.", 5)
            if not paging.get("next"):
                return result
            cursors = paging.get("cursors", {})
            after = cursors.get("after") if isinstance(cursors, dict) else None
            if not isinstance(after, str) or not after or after in seen:
                raise AppError("INCOMPLETE_DATA", "Nie można pobrać wszystkich stron API.", 5)
            seen.add(after)
            query["after"] = after
        raise AppError("INCOMPLETE_DATA", "Przekroczono limit stron; zawęź okres raportu.", 5)


def check_connection(root: Path, client: str) -> dict:
    connection = load_connection(root, client)
    status = connection_status(root, client)
    if status["missing_requirements"]:
        raise AppError("CONFIG_REQUIRED", "Konfiguracja jest niepełna; sprawdź auth status.", 3)
    credentials = load_credentials(root, connection)
    api = MetaReadClient(connection, credentials)
    account = api.get("account")
    if account.get("id") != connection.account_id:
        raise AppError("SCOPE_MISMATCH", "Odpowiedź API dotyczy innego konta.", 3)
    insights = api.get("insights")
    if not isinstance(insights.get("data"), list):
        raise AppError("API_RESPONSE", "Niepoprawna odpowiedź testu raportowania.", 5)
    return {
        "client_id": client,
        "source": "meta",
        "status": "VERIFIED",
        "account": {
            key: account.get(key)
            for key in ("id", "name", "account_id", "currency", "timezone_name", "account_status")
        },
        "verified_checks": ["account_read", "insights_read"],
        "token_expiry_checked": False,
        "app_identity_verified": False,
        "reporting_implemented": True,
        "writes": connection.access_mode == "approved_create_paused",
        "write_access_verified": False,
    }
