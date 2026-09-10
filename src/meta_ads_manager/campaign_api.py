"""Account-scoped discovery and a private create-only transport for the executor."""

import hashlib
import hmac
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from meta_ads_manager.account_policy import validate_read_params
from meta_ads_manager.decision_store import fail
from meta_ads_manager.errors import AppError
from meta_ads_manager.meta_connection import NoRedirect, api_error

EDGES = {"campaigns", "adsets", "ads", "adcreatives"}
CREATE_FIELDS = {
    "campaigns": {
        "name",
        "objective",
        "status",
        "special_ad_categories",
        "buying_type",
        "is_adset_budget_sharing_enabled",
    },
    "adsets": {
        "name",
        "campaign_id",
        "status",
        "optimization_goal",
        "destination_type",
        "billing_event",
        "bid_strategy",
        "promoted_object",
        "daily_budget",
        "lifetime_budget",
        "start_time",
        "end_time",
        "dsa_beneficiary",
        "dsa_payor",
        "targeting",
    },
    "adcreatives": {"name", "object_story_spec", "url_tags"},
    "ads": {"name", "adset_id", "creative", "status"},
}


class CampaignAPI:
    def __init__(self, connection, credentials):
        self.connection, self.credentials = connection, credentials
        self.account = connection.account_id
        if not self.account or connection.api_version != "v26.0":
            fail("CONFIG_REQUIRED", "Kreator wymaga konta i wersji API v26.0.")
        self.opener = build_opener(NoRedirect())
        self.pages_allowed, self.objects_allowed = set(), set()

    def _request(self, path, params, *, method="GET", authorization=None):
        from meta_ads_manager.campaign_executor import authorize_request

        validate_read_params(params)
        if method not in ("GET", "POST") or "access_token" in params:
            fail("WRITE_POLICY", "Niedozwolona metoda lub parametr zapytania.")
        if method == "POST":
            edge = path.removeprefix(self.account + "/")
            if (
                path != f"{self.account}/{edge}"
                or edge not in EDGES
                or not set(params).issubset(CREATE_FIELDS[edge])
            ):
                fail("UNSUPPORTED_OPERATION", "Niedozwolony zapis poza planem tworzenia.")
            if self.connection.access_mode != "approved_create_paused":
                fail("READ_ONLY_VIOLATION", "Konfiguracja dopuszcza tylko odczyt.")
            if edge != "adcreatives" and params.get("status") != "PAUSED":
                fail("WRITE_POLICY", "Dozwolony status to PAUSED.")
            authorize_request(authorization, self.connection, edge, params)
        token = self.credentials.access_token.get_secret_value()
        params = dict(params)
        if self.credentials.app_secret:
            params["appsecret_proof"] = hmac.new(
                self.credentials.app_secret.get_secret_value().encode(),
                token.encode(),
                hashlib.sha256,
            ).hexdigest()
        encoded = urlencode(
            {
                k: json.dumps(v) if isinstance(v, (dict, list, bool)) else v
                for k, v in params.items()
            }
        )
        url = f"https://graph.facebook.com/{self.connection.api_version}/{path}"
        request = Request(
            url + ("?" + encoded if method == "GET" else ""),
            data=encoded.encode() if method == "POST" else None,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method=method,
        )
        try:
            with self.opener.open(request, timeout=30) as response:
                result = json.load(response)
        except HTTPError as exc:
            try:
                error = json.loads(exc.read())
            except (ValueError, OSError):
                error = {}
            raise api_error(error if isinstance(error, dict) else {}) from None
        except (URLError, TimeoutError, OSError):
            fail("NETWORK_ERROR", "Nie otrzymano pewnego wyniku z Meta; sprawdź stan operacji.")
        except ValueError:
            fail("API_RESPONSE", "Niepoprawna odpowiedź Meta.")
        if not isinstance(result, dict):
            fail("API_RESPONSE", "Niepoprawna odpowiedź Meta.")
        if "error" in result:
            raise api_error(result)
        return result

    def get(self, path, params):
        validate_read_params(params)
        if "access_token" in params:
            fail("READ_ONLY_VIOLATION", "Token nie może być parametrem zapytania.")
        allowed = {self.account} | {
            f"{self.account}/{e}"
            for e in EDGES | {"promote_pages", "adspixels", "adimages", "customconversions"}
        }
        allowed |= {f"{p}/leadgen_forms" for p in self.pages_allowed} | self.objects_allowed
        if path not in allowed:
            fail("SCOPE_MISMATCH", "Obiekt nie należy do zakresu kreatora.")
        return self._request(path, params)

    def list(self, edge, fields, *, page_id=None):
        if page_id and (edge != "leadgen_forms" or page_id not in self.pages_allowed):
            fail("SCOPE_MISMATCH", "Strona nie jest zasobem reklamowym tego konta.")
        path = f"{page_id or self.account}/{edge}"
        params, result, seen = {"fields": fields, "limit": 100}, [], set()
        for _ in range(1000):
            payload = self.get(path, params)
            rows = payload.get("data")
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                fail("API_RESPONSE", "Niepoprawna lista zasobów.")
            result.extend(rows)
            paging = payload.get("paging", {})
            if not paging.get("next"):
                if edge == "promote_pages":
                    self.pages_allowed |= {
                        r["id"]
                        for r in result
                        if isinstance(r.get("id"), str) and r["id"].isdigit()
                    }
                return result
            after = paging.get("cursors", {}).get("after")
            if not isinstance(after, str) or not after or after in seen:
                fail("INCOMPLETE_DATA", "Niepełna lista zasobów Meta.")
            seen.add(after)
            params["after"] = after
        fail("INCOMPLETE_DATA", "Przekroczono limit stron zasobów.")

    def account_state(self):
        state = self.get(self.account, {"fields": "id,name,currency,timezone_name,account_status"})
        if state.get("id") != self.account:
            fail("SCOPE_MISMATCH", "Meta zwróciła inne konto.")
        return state

    def inventory(self, page_id=None):
        result = {"account": self.account_state(), "resources": {}, "errors": []}
        for edge, fields in (
            ("promote_pages", "id,name"),
            ("adspixels", "id,name"),
            ("adimages", "hash,name,width,height,url"),
            ("customconversions", "id,name,pixel,custom_event_type"),
        ):
            try:
                result["resources"][edge] = self.list(edge, fields)
            except AppError as exc:
                result["errors"].append({"resource": edge, "code": exc.code})
        if page_id:
            try:
                result["resources"]["leadgen_forms"] = self.list(
                    "leadgen_forms", "id,name,status", page_id=page_id
                )
            except AppError as exc:
                result["errors"].append({"resource": "leadgen_forms", "code": exc.code})
        return result

    def preflight(self, brief):
        account = self.account_state()
        if (account.get("currency"), account.get("timezone_name")) != (
            brief.currency,
            brief.timezone,
        ):
            fail("STATE_CONFLICT", "Waluta lub strefa konta różni się od briefu.")
        if account.get("account_status") != 1:
            fail("ACCOUNT_UNAVAILABLE", "Konto nie jest aktywne.")

        def select(rows, key, expected):
            found = [r for r in rows if r.get(key) == expected]
            if len(found) != 1:
                fail("ASSET_REQUIRED", "Nie znaleziono jednoznacznego zasobu z briefu.")
            return found[0]

        result = {
            "account": account,
            "page": select(self.list("promote_pages", "id,name"), "id", brief.page_id),
        }
        images = self.list("adimages", "hash,width,height")
        result["images"] = [
            select(images, "hash", key)
            for key in sorted({a.image_hash for s in brief.adsets for a in s.ads})
        ]
        if brief.lead_form_id:
            form = select(
                self.list("leadgen_forms", "id,name,status", page_id=brief.page_id),
                "id",
                brief.lead_form_id,
            )
            if form.get("status") != "ACTIVE":
                fail("ASSET_REQUIRED", "Formularz nie jest aktywny.")
            result["form"] = form
        if brief.pixel_id:
            result["pixel"] = select(self.list("adspixels", "id,name"), "id", brief.pixel_id)
        if brief.custom_conversion_id:
            custom = select(
                self.list("customconversions", "id,name,pixel,custom_event_type"),
                "id",
                brief.custom_conversion_id,
            )
            if custom.get("pixel", {}).get("id") != brief.pixel_id:
                fail("ASSET_REQUIRED", "Konwersja należy do innego piksela.")
            result["custom_conversion"] = custom
        return result

    def _create(self, edge, params, *, authorization=None):
        result = self._request(
            f"{self.account}/{edge}", params, method="POST", authorization=authorization
        )
        if not isinstance(result.get("id"), str) or not re.fullmatch(r"[0-9]+", result["id"]):
            fail("API_RESPONSE", "Meta nie zwróciła identyfikatora utworzonego obiektu.")
        return result["id"]

    def read_created(self, identifier, edge, params):
        if not re.fullmatch(r"[0-9]+", identifier):
            fail("API_RESPONSE", "Niepoprawny identyfikator obiektu.")
        self.objects_allowed.add(identifier)
        fields = set(params) | {"id", "account_id"}
        return self.get(identifier, {"fields": ",".join(sorted(fields))})
