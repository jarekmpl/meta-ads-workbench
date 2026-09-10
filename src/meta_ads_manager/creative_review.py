"""Read-only creative pilot: scoped raw evidence, stratified sample, honest coverage."""

import hashlib
import hmac
import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from meta_ads_manager.account_policy import validate_read_params
from meta_ads_manager.errors import AppError
from meta_ads_manager.meta_connection import NoRedirect, api_error, load_credentials, save_private
from meta_ads_manager.meta_provider import MetaProvider, report_period, validate_scope

NATIVE_LEAD = "onsite_conversion.lead_grouped"
WEB_LEAD = "offsite_conversion.fb_pixel_lead"
FIELDS = (
    "account_id,account_currency,ad_id,ad_name,adset_id,adset_name,campaign_id,campaign_name,"
    "date_start,date_stop,spend,impressions,inline_link_clicks,reach,frequency,actions,action_values"
)
VIDEO_FIELDS = (
    "account_id,account_currency,ad_id,date_start,date_stop,video_play_actions,"
    "video_p25_watched_actions,video_p50_watched_actions,video_p75_watched_actions,"
    "video_p95_watched_actions,video_p100_watched_actions,video_avg_time_watched_actions,"
    "video_thruplay_watched_actions"
)
CREATIVE_FIELDS = (
    "id,name,body,title,call_to_action_type,image_hash,image_url,thumbnail_url,video_id,"
    "object_story_spec,asset_feed_spec,effective_object_story_id,link_url,url_tags,"
    "degrees_of_freedom_spec"
)


def number(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0:
            raise ValueError
        return result
    except Exception:
        raise AppError("API_RESPONSE", "Niepoprawna nieujemna wartość liczbowa.", 5) from None


def action(row, action_type, window="7d_click"):
    """Only explicit windows; missing window is unreported, not a measured zero."""
    items = [x for x in row.get("actions", []) if x.get("action_type") == action_type]
    if len(items) > 1:
        raise AppError("API_RESPONSE", "Powtórzony typ zdarzenia.", 5)
    return number(items[0][window]) if items and window in items[0] else None


def ratio(a, b, factor=1):
    return str(a / b * factor) if a is not None and b is not None and b > 0 else None


def metrics(row):
    spend, impressions = number(row["spend"]), number(row["impressions"])
    clicks = number(row.get("inline_link_clicks", "0"))
    leads, web = action(row, NATIVE_LEAD), action(row, WEB_LEAD)
    return {
        "spend": str(spend), "impressions": str(impressions), "link_clicks": str(clicks),
        "reach": row.get("reach"), "frequency": row.get("frequency"),
        "native_leads_7d_click": str(leads) if leads is not None else None,
        "web_leads_7d_click": str(web) if web is not None else None,
        "native_cpl_7d_click": ratio(spend, leads),
        "web_cpl_7d_click": ratio(spend, web),
        "link_ctr_percent": ratio(clicks, impressions, 100),
        "link_cpc": ratio(spend, clicks), "cpm": ratio(spend, impressions, 1000),
    }


def choose_sample(rows, size):
    """Campaign coverage, spend coverage, then low-exposure candidates; no winner labels."""
    if not 1 <= size <= 50:
        raise AppError("VALIDATION_ERROR", "Próba powinna obejmować 1-50 reklam.", 2)
    eligible = sorted(
        [r for r in rows if number(r["impressions"]) > 0],
        key=lambda r: (-number(r["spend"]), r["ad_id"]),
    )
    selected, reasons, campaigns = [], {}, set()

    def add(row, reason):
        if len(selected) < size and row["ad_id"] not in reasons:
            selected.append(row["ad_id"])
            reasons[row["ad_id"]] = reason

    for row in eligible:
        if row["campaign_id"] not in campaigns and len(selected) < max(1, size // 2):
            add(row, "campaign_coverage")
            campaigns.add(row["campaign_id"])
    for row in eligible:
        if len(selected) >= max(1, size - size // 4):
            break
        add(row, "spend_coverage")
    for row in reversed(eligible):
        add(row, "low_exposure_comparison")
    return selected, reasons


class CreativeAPI:
    """Account paths plus IDs learned from validated account Insights. GET only."""

    def __init__(self, connection, credentials):
        self.connection, self.credentials = connection, credentials
        self.allowed_nodes = {connection.account_id}
        self.opener = build_opener(NoRedirect())

    def allow(self, node):
        if not isinstance(node, str) or not re.fullmatch(r"[0-9]+(?:_[0-9]+)?", node):
            raise AppError("API_RESPONSE", "Niepoprawny identyfikator obiektu.", 5)
        self.allowed_nodes.add(node)

    def get(self, path, params):
        parts = path.split("/")
        if parts[0] not in self.allowed_nodes or len(parts) > 2:
            raise AppError("SCOPE_MISMATCH", "Obiekt poza zakresem odczytu.", 3)
        if len(parts) == 2 and parts[1] not in ("insights", "adimages", "thumbnails"):
            raise AppError("UNSUPPORTED_OPERATION", "Nieobsługiwany odczyt.", 2)
        if "access_token" in params:
            raise AppError("VALIDATION_ERROR", "Token nie może być w URL.", 2)
        query = dict(params)
        validate_read_params(query)
        token = self.credentials.access_token.get_secret_value()
        if self.credentials.app_secret:
            query["appsecret_proof"] = hmac.new(
                self.credentials.app_secret.get_secret_value().encode(), token.encode(),
                hashlib.sha256,
            ).hexdigest()
        request = Request(
            f"https://graph.facebook.com/{self.connection.api_version}/{path}?{urlencode(query)}",
            headers={"Authorization": f"Bearer {token}"}, method="GET",
        )
        try:
            with self.opener.open(request, timeout=60) as response:
                result = json.load(response)
        except HTTPError as exc:
            try:
                body = json.loads(exc.read())
            except (ValueError, OSError):
                body = {}
            raise api_error(body if isinstance(body, dict) else {}) from None
        except (URLError, TimeoutError, OSError):
            raise AppError("NETWORK_ERROR", "Nie udało się pobrać danych kreacji.", 5) from None
        except ValueError:
            raise AppError("API_RESPONSE", "Niepoprawna odpowiedź API.", 5) from None
        if not isinstance(result, dict):
            raise AppError("API_RESPONSE", "Niepoprawna odpowiedź API.", 5)
        if "error" in result:
            raise api_error(result)
        return result

    def pages(self, path, params):
        result, seen, query = [], set(), dict(params)
        for _ in range(1000):
            payload = self.get(path, query)
            rows = payload.get("data")
            if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
                raise AppError("API_RESPONSE", "Niepoprawna lista wyników.", 5)
            result.extend(rows)
            paging = payload.get("paging", {})
            if not isinstance(paging, dict):
                raise AppError("API_RESPONSE", "Niepoprawna paginacja.", 5)
            if not paging.get("next"):
                return result
            after = paging.get("cursors", {}).get("after")
            if not isinstance(after, str) or not after or after in seen:
                raise AppError("INCOMPLETE_DATA", "Niepełna paginacja kreacji.", 5)
            seen.add(after)
            query["after"] = after
        raise AppError("INCOMPLETE_DATA", "Przekroczono limit stron.", 5)


class Evidence:
    """Resume only identical scoped requests; errors remain explicit, never zero rows."""

    def __init__(self, directory, scope):
        self.directory, self.scope = directory, scope
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        marker = directory / "scope.json"
        if marker.exists():
            if json.loads(marker.read_text()) != scope:
                raise AppError("SCOPE_MISMATCH", "Katalog zawiera inny zakres analizy.", 3)
        else:
            save_private(marker, scope)
        self.errors = []

    def fetch(self, name, api, path, params, many=True, optional=False):
        file = self.directory / (name + ".json")
        spec = {"path": path, "params": params}
        if file.exists():
            payload = json.loads(file.read_text())
            if payload["scope"] != self.scope or payload["request"] != spec:
                raise AppError("SCOPE_MISMATCH", "Niezgodny zapisany odczyt.", 3)
            return payload["data"]
        try:
            data = api.pages(path, params) if many else api.get(path, params)
        except AppError as exc:
            if not optional or exc.code in ("AUTH_REQUIRED", "SCOPE_MISMATCH"):
                raise
            self.errors.append({"dataset": name, "code": exc.code})
            return None
        save_private(file, {
            "scope": self.scope, "request": spec, "fetched_at": datetime.now(UTC).isoformat(),
            "complete_pagination": many, "data": data,
        })
        return data


def validate_rows(rows, account, currency, since, until, level="ad", daily=False):
    seen = set()
    for row in rows:
        MetaProvider.validate_row_scope(row, account.removeprefix("act_"), currency)
        start, stop = row.get("date_start"), row.get("date_stop")
        if not isinstance(start, str) or not isinstance(stop, str):
            raise AppError("API_RESPONSE", "Brak dat wyników.", 5)
        if not str(since) <= start <= stop <= str(until):
            raise AppError("SCOPE_MISMATCH", "Wyniki poza okresem.", 3)
        if daily and start != stop:
            raise AppError("SCOPE_MISMATCH", "Wynik nie jest dzienny.", 3)
        if not daily and (start, stop) != (str(since), str(until)):
            raise AppError("SCOPE_MISMATCH", "Niepełny zakres wyniku.", 3)
        key = (row.get("ad_id") if level == "ad" else account, start, stop,
               row.get("publisher_platform"), row.get("platform_position"))
        if key in seen:
            raise AppError("INCOMPLETE_DATA", "Powtórzony wiersz wyników.", 5)
        seen.add(key)
        if level == "ad" and not re.fullmatch(r"[0-9]+", row.get("ad_id", "")):
            raise AppError("API_RESPONSE", "Brak ID reklamy.", 5)


def collect(args):
    if not 1 <= args.sample_size <= 50:
        raise AppError("VALIDATION_ERROR", "Próba powinna obejmować 1-50 reklam.", 2)
    root = Path.cwd()
    connection = validate_scope(root, args.client, args.account)
    api = CreativeAPI(connection, load_credentials(root, connection))
    account = api.get(args.account, {
        "fields": "id,account_id,name,currency,timezone_name",
    })
    if account.get("id") != args.account:
        raise AppError("SCOPE_MISMATCH", "Odczytano inne konto.", 3)
    since, until = report_period(args, account["timezone_name"])
    previous_until = since - timedelta(days=1)
    previous_since = previous_until - (until - since)
    scope = {
        "client_id": args.client, "account_id": args.account, "since": str(since),
        "until": str(until), "api_version": connection.api_version,
        "sample_size": args.sample_size, "collector_version": "1",
        "attribution": ["7d_click", "1d_view"], "action_report_time": "impression",
    }
    evidence = Evidence(args.directory, scope)
    if not (args.directory / "account.json").exists():
        save_private(args.directory / "account.json", account)
    datasets = {}
    checks = {}
    for label, start, stop in [
        ("current", since, until), ("previous", previous_since, previous_until),
    ]:
        params = {
            "fields": FIELDS, "level": "ad", "limit": "500",
            "time_range": json.dumps({"since": str(start), "until": str(stop)}),
            "action_attribution_windows": json.dumps(["7d_click", "1d_view"]),
            "action_report_time": "impression",
        }
        rows = evidence.fetch(f"ads-{label}", api, args.account + "/insights", params)
        validate_rows(rows, args.account, account["currency"], start, stop)
        datasets[label] = rows
        total_params = {**params, "level": "account", "fields": (
            "account_id,account_currency,date_start,date_stop,spend,impressions,inline_link_clicks"
        )}
        totals = evidence.fetch(f"account-{label}", api, args.account + "/insights", total_params)
        validate_rows(totals, args.account, account["currency"], start, stop, level="account")
        if len(totals) > 1 or (rows and not totals):
            raise AppError("INCOMPLETE_DATA", "Brak kontrolnego podsumowania konta.", 5)
        checks[label] = {
            k: str(sum((number(r.get(k, "0")) for r in rows), Decimal(0))
                   - number(totals[0].get(k, "0") if totals else "0"))
            for k in ("spend", "impressions", "inline_link_clicks")
        }
    selected, reasons = choose_sample(datasets["current"], args.sample_size)
    if not selected:
        raise AppError("INSUFFICIENT_DATA", "Brak reklam z emisją w badanym okresie.", 6)
    by_current = {r["ad_id"]: r for r in datasets["current"]}
    by_previous = {r["ad_id"]: r for r in datasets["previous"]}
    cards = []
    for ad_id in selected:
        api.allow(ad_id)
        fields = (
            "id,account_id,name,campaign_id,adset_id,status,effective_status,created_time,"
            "updated_time,creative{" + CREATIVE_FIELDS + "},"
            "campaign{id,name,objective},adset{id,name,optimization_goal,destination_type,"
            "promoted_object,attribution_spec,targeting,daily_budget,lifetime_budget}"
        )
        ad = evidence.fetch(f"ad-{ad_id}", api, ad_id, {"fields": fields},
                            many=False, optional=True)
        if ad is not None:
            row = by_current[ad_id]
            if (ad.get("id") != ad_id or ad.get("account_id") != args.account[4:]
                    or ad.get("campaign_id") != row["campaign_id"]
                    or ad.get("adset_id") != row["adset_id"]):
                raise AppError("SCOPE_MISMATCH", "Reklama nie pasuje do wyników.", 3)
        cards.append({
            "ad_id": ad_id, "selection_reason": reasons[ad_id],
            "settings_available": ad is not None,
            "current": metrics(by_current[ad_id]),
            "previous": metrics(by_previous[ad_id]) if ad_id in by_previous else None,
            "content_review": {"status": "pending", "observations": []},
        })
    common = {
        "level": "ad", "limit": "500", "action_report_time": "impression",
        "action_attribution_windows": json.dumps(["7d_click", "1d_view"]),
        "filtering": json.dumps([{"field": "ad.id", "operator": "IN", "value": selected}]),
    }
    for label, extra, start in [
        ("daily", {"fields": FIELDS, "time_increment": "1"}, previous_since),
        ("placements", {"fields": FIELDS, "breakdowns": "publisher_platform,platform_position"},
         since),
        ("video", {"fields": VIDEO_FIELDS}, since),
    ]:
        rows = evidence.fetch(label, api, args.account + "/insights", {
            **common, **extra,
            "time_range": json.dumps({"since": str(start), "until": str(until)}),
        }, optional=True)
        if rows is not None:
            validate_rows(rows, args.account, account["currency"], start, until,
                          daily=label == "daily")
            if any(r["ad_id"] not in selected for r in rows):
                raise AppError("SCOPE_MISMATCH", "Wynik spoza próby kreacji.", 3)
    source_hashes = {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                     for f in args.directory.glob("*.json") if f.name not in ("collection.json",)}
    result = {
        "schema_version": "1.0", "kind": "creative_collection", **scope,
        "source": "meta", "coverage": "partial", "account": account,
        "previous_since": str(previous_since), "previous_until": str(previous_until),
        "selected_ad_ids": selected, "cards": cards, "reconciliation_differences": checks,
        "all_ads_current": len(datasets["current"]), "all_ads_previous": len(datasets["previous"]),
        "source_hashes": source_hashes, "errors": evidence.errors,
        "limitations": [
            "Pilot is a purposive sample, not a randomized experiment.",
            "Settings are current at fetch time; historical creative identity is unverified.",
            "Per-asset attribution, audio and landing pages require separate review.",
            "Missing explicit action windows are null, not measured zero.",
        ],
    }
    save_private(args.directory / "collection.json", result)
    return {"directory": str(args.directory.resolve()), "selected_ads": len(selected),
            "all_ads_current": len(datasets["current"]), "errors": evidence.errors,
            "reconciliation_differences": checks, "coverage": "partial"}
