"""Deterministic names and payloads from an explicitly confirmed brief."""

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from meta_ads_manager.campaign_models import CreationBrief
from meta_ads_manager.decision_store import canonical, fail

TECHNICAL = {"currency", "timezone"}
OPTIONAL = {"lead_form_id", "pixel_id", "custom_conversion_id"}
EDITABLE = set(CreationBrief.model_fields) - {
    "schema_version",
    "kind",
    "client_id",
    "account_id",
    "project_id",
}
QUESTIONS = {
    "goal_kind": "Jaki jest cel kampanii: leady, sprzedaż, rejestracje czy sprzedaż biletów?",
    "offer": "Jaką ofertę promujemy i jakie warunki mają obowiązywać w kampanii?",
    "landing_url": "Jaki jest adres strony oferty? Sprawdzę jej treść przed dalszym planowaniem.",
    "measurement": (
        "Który wynik możemy mierzyć: formularz Meta, lead na stronie, zakup, "
        "rejestrację czy własną konwersję pomocniczą?"
    ),
    "result_definition": "Co dokładnie uznajemy za wynik tej kampanii?",
    "goal_id": "Do którego zapisanego celu biznesowego przypisujemy kampanię?",
    "goal_revision": "Która wersja ustalonego celu ma obowiązywać?",
    "client_code": "Jakiego krótkiego kodu klienta używamy w nazwach?",
    "project_code": "Jak nazywamy projekt lub ofertę w strukturze konta?",
    "language": (
        "W jakim języku mają być reklamy? Język tekstu nie ogranicza automatycznie odbiorców."
    ),
    "role": "Czy jest to kampania główna, czy osobna kampania testowa?",
    "currency": "Jaka jest waluta konta? Pobiorę ją z Meta.",
    "timezone": "Jaka jest strefa czasowa konta? Pobiorę ją z Meta.",
    "budget_period": "Czy budżety zestawów mają być dzienne, czy całkowite na wskazany okres?",
    "start_time": "Kiedy kampania ma się rozpocząć? Podaj datę i godzinę w strefie konta.",
    "end_time": "Kiedy kampania ma się zakończyć?",
    "page_id": "Którą stroną na Facebooku podpisujemy reklamy? Pokażę dostępne strony.",
    "lead_form_id": (
        "Którego istniejącego formularza Meta używamy? Pokażę formularze wybranej strony."
    ),
    "pixel_id": "Który dostępny piksel mierzy wynik na stronie?",
    "custom_conversion_id": (
        "Która konwersja niestandardowa odpowiada uzgodnionemu kliknięciu do zakupu?"
    ),
    "special_ad_categories": (
        "Czy reklama podlega kategorii szczególnej? Obecny wykonawca "
        "obsługuje kampanie bez takich kategorii."
    ),
    "dsa_beneficiary": "Jaka firma jest beneficjentem reklamy?",
    "dsa_payor": "Jaka firma płaci za reklamę?",
    "placements": (
        "Pierwszy wykonawca obsługuje aktualności Facebooka. Czy przygotowujemy ten wariant?"
    ),
    "adsets": (
        "Ustalmy zestawy: kraje, wiek odbiorców, budżety i gotowe reklamy z "
        "obrazami dostępnymi na koncie."
    ),
    "followup_process": (
        "Jak obsłużymy uzyskane wyniki, np. kontakt z leadem lub potwierdzenie rejestracji?"
    ),
    "test_hypothesis": "Jaką hipotezę sprawdzamy w pierwszym teście?",
    "test_success": "Po czym poznamy, że test się udał?",
    "test_review": "Kiedy ocenimy wyniki testu?",
    "stop_condition": "W jakiej sytuacji operator powinien przerwać test?",
    "rights_confirmed": "Czy mamy prawo użyć wybranych materiałów i treści?",
    "measurement_confirmed": (
        "Czy wybrany pomiar został sprawdzony i odpowiada uzgodnionej definicji wyniku?"
    ),
}
DEPENDENCIES = {
    "goal_kind": {
        "measurement",
        "goal_id",
        "goal_revision",
        "result_definition",
        "measurement_confirmed",
    },
    "measurement": {
        "goal_id",
        "goal_revision",
        "result_definition",
        "lead_form_id",
        "pixel_id",
        "custom_conversion_id",
        "measurement_confirmed",
        "adsets",
    },
    "landing_url": {"offer", "measurement_confirmed", "adsets", "rights_confirmed"},
    "page_id": {"lead_form_id", "adsets"},
    "goal_id": {"goal_revision", "result_definition", "measurement_confirmed"},
    "currency": {"adsets"},
    "timezone": {"start_time", "end_time"},
    "adsets": {"rights_confirmed"},
    "offer": {"adsets", "test_hypothesis", "test_success"},
    "pixel_id": {"custom_conversion_id", "measurement_confirmed"},
    "custom_conversion_id": {"measurement_confirmed"},
    "lead_form_id": {"measurement_confirmed"},
    "goal_revision": {"result_definition", "measurement_confirmed", "test_success"},
    "budget_period": {"adsets", "stop_condition"},
    "end_time": {"test_review"},
    "start_time": {"test_review"},
}


def requirements(fields):
    required = EDITABLE - OPTIONAL
    measurement = fields.get("measurement", {}).get("value")
    if measurement == "lead_form":
        required |= {"lead_form_id"}
    elif measurement in ("web_lead", "purchase", "registration", "custom_proxy"):
        required |= {"pixel_id"}
    if measurement == "custom_proxy":
        required |= {"custom_conversion_id"}
    return required


def readiness(draft):
    fields = draft["fields"]
    missing = [
        key
        for key in QUESTIONS
        if key in requirements(fields)
        and (key not in fields or fields[key]["state"] != "confirmed")
    ]
    return {
        "ready": not missing,
        "missing": missing,
        "questions": [{"field": key, "question": QUESTIONS[key]} for key in missing[:3]],
    }


def complete(draft):
    ready = readiness(draft)
    if not ready["ready"]:
        fail("BRIEF_INCOMPLETE", "Uzupełnij lub potwierdź pola: " + ", ".join(ready["missing"]))
    fields = {
        key: row["value"] for key, row in draft["fields"].items() if row["state"] == "confirmed"
    }
    for key in OPTIONAL:
        if key not in requirements(draft["fields"]):
            fields[key] = None
    return CreationBrief.model_validate_json(
        canonical(
            {
                "schema_version": "1.0",
                "kind": "creation_brief",
                "client_id": draft["client_id"],
                "account_id": draft["account_id"],
                "project_id": draft["project_id"],
                **fields,
            }
        )
    )


def code(text):
    text = unicodedata.normalize("NFKD", text.replace("ł", "l").replace("Ł", "L"))
    token = re.sub(r"[^A-Z0-9]+", "-", text.encode("ascii", "ignore").decode().upper()).strip("-")
    if not token or len(token) > 32:
        fail("NAMING_CODE", "Kod nazwy jest pusty lub przekracza 32 znaki ASCII.")
    return token


def name(*tokens):
    result = " | ".join(tokens)
    if len(result) > 200:
        fail(
            "NAMING_LENGTH", "Skróć uzgodnione kody; nazwa przekracza limit generatora 200 znaków."
        )
    return result


def digest(plan):
    return hashlib.sha256(
        canonical({k: v for k, v in plan.items() if k != "plan_hash"}).encode()
    ).hexdigest()


def compile_plan(brief, keys, *, draft_id, revision, api_version, resources, goal):
    if brief.start_time <= datetime.now(UTC):
        fail("SCHEDULE_EXPIRED", "Początek kampanii musi być w przyszłości.")
    if api_version != "v26.0":
        fail("API_VERSION", "Wykonawca jest ograniczony do API v26.0.")
    ckey, skeys, akeys = keys["campaign"], keys["adsets"], iter(keys["ads"])
    measurement = brief.measurement
    objective = "OUTCOME_SALES" if measurement == "purchase" else "OUTCOME_LEADS"
    if measurement == "custom_proxy":
        objective = "OUTCOME_SALES"
    business = {"leads": "LEAD", "registrations": "REG", "sales": "SALE", "tickets": "SALE"}[
        brief.goal_kind
    ]
    markets = sorted({c for s in brief.adsets for c in s.countries})
    market = markets[0] if len(markets) == 1 else "MULTI"
    cname = name(
        code(brief.client_code),
        code(brief.project_code),
        business,
        market + "-" + brief.language.upper(),
        brief.role,
        ckey,
    )
    ops = [
        {
            "key": ckey,
            "edge": "campaigns",
            "params": {
                "name": cname,
                "objective": objective,
                "status": "PAUSED",
                "special_ad_categories": [],
                "buying_type": "AUCTION",
                "is_adset_budget_sharing_enabled": False,
            },
        }
    ]
    for index, adset in enumerate(brief.adsets):
        skey = skeys[index]
        if measurement == "lead_form":
            promoted, optimization, destination = (
                {"page_id": brief.page_id},
                "LEAD_GENERATION",
                "ON_AD",
            )
        else:
            promoted = {"pixel_id": brief.pixel_id}
            if measurement == "custom_proxy":
                promoted["custom_conversion_id"] = brief.custom_conversion_id
            else:
                promoted["custom_event_type"] = {
                    "purchase": "PURCHASE",
                    "web_lead": "LEAD",
                    "registration": "COMPLETE_REGISTRATION",
                }[measurement]
            optimization, destination = "OFFSITE_CONVERSIONS", "WEBSITE"
        measurement_code = {
            "lead_form": "LEAD",
            "web_lead": "LEAD",
            "purchase": "PURCHASE",
            "registration": "REG-CONF",
            "custom_proxy": "OUTCLICK",
        }[measurement]
        sname = name(
            ckey,
            measurement_code,
            "FORM" if measurement == "lead_form" else "WEB",
            adset.audience_code,
            "-".join(adset.countries),
            skey,
        )
        params = {
            "name": sname,
            "campaign_id": {"ref": ckey},
            "status": "PAUSED",
            "optimization_goal": optimization,
            "destination_type": destination,
            "billing_event": "IMPRESSIONS",
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "promoted_object": promoted,
            brief.budget_period + "_budget": int(adset.budget * 100),
            "start_time": brief.start_time.isoformat(),
            "end_time": brief.end_time.isoformat(),
            "dsa_beneficiary": brief.dsa_beneficiary,
            "dsa_payor": brief.dsa_payor,
            "targeting": {
                "geo_locations": {"countries": adset.countries},
                "age_min": adset.age_min,
                "age_max": adset.age_max,
                "publisher_platforms": ["facebook"],
                "facebook_positions": ["feed"],
                "targeting_automation": {"advantage_audience": 0},
            },
        }
        ops.append({"key": skey, "edge": "adsets", "params": params})
        for ad in adset.ads:
            akey = next(akeys)
            aname = name(skey, code(ad.concept), "IMG", f"V{ad.version:02}", akey)
            cta_value = (
                {"lead_gen_form_id": brief.lead_form_id}
                if measurement == "lead_form"
                else {"link": brief.landing_url}
            )
            link_data = {
                "link": brief.landing_url,
                "message": ad.message,
                "name": ad.headline,
                "description": ad.description,
                "image_hash": ad.image_hash,
                "call_to_action": {"type": ad.cta, "value": cta_value},
            }
            if not ad.description:
                link_data.pop("description")
            creative_key = akey + "-CREATIVE"
            ops.append(
                {
                    "key": creative_key,
                    "edge": "adcreatives",
                    "params": {
                        "name": aname + " | CREATIVE",
                        "object_story_spec": {"page_id": brief.page_id, "link_data": link_data},
                        "url_tags": "utm_source=facebook&utm_medium=paid_social"
                        f"&utm_campaign={ckey}&utm_content={akey}",
                    },
                }
            )
            ops.append(
                {
                    "key": akey,
                    "edge": "ads",
                    "params": {
                        "name": aname,
                        "adset_id": {"ref": skey},
                        "creative": {"creative_id": {"ref": creative_key}},
                        "status": "PAUSED",
                    },
                }
            )
    now = datetime.now(UTC)
    plan = {
        "kind": "campaign_creation_plan",
        "schema_version": "1.0",
        "client_id": brief.client_id,
        "account_id": brief.account_id,
        "draft_id": draft_id,
        "draft_revision": revision,
        "api_version": api_version,
        "created_at": now.isoformat(),
        "expires_at": min(now + timedelta(hours=24), brief.start_time).isoformat(),
        "policy_version": "2026-09-10",
        "brief": brief.model_dump(mode="json"),
        "resources": resources,
        "goal": goal,
        "keys": keys,
        "operations": ops,
        "budget_summary": {
            "level": "adset",
            "period": brief.budget_period,
            "currency": brief.currency,
            "amount": str(sum((s.budget for s in brief.adsets), Decimal(0))),
            "initial_status": "PAUSED",
        },
    }
    plan["plan_hash"] = digest(plan)
    return plan


def resolve(value, ids):
    if isinstance(value, dict):
        if set(value) == {"ref"}:
            if value["ref"] not in ids:
                fail("DEPENDENCY_REQUIRED", "Brak zweryfikowanego obiektu nadrzędnego.")
            return ids[value["ref"]]
        return {k: resolve(v, ids) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, ids) for v in value]
    return value


def plan_markdown(plan):
    lines = [
        "# Plan utworzenia kampanii",
        "",
        f"Klient: {plan['client_id']}; konto: {plan['account_id']}.",
        f"Plan: {plan['plan_hash']}",
        f"Ważny do: {plan['expires_at']}",
        "",
        "Wszystkie kampanie, zestawy i reklamy powstaną jako PAUSED. Aktywacja jest osobną zmianą.",
        "",
        "## Brief",
        "",
        "```json",
        json.dumps(plan["brief"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Budżet",
        "",
        json.dumps(plan["budget_summary"], ensure_ascii=False),
        "",
        "## Dokładne operacje",
    ]
    for op in plan["operations"]:
        lines += [
            "",
            f"### {op['key']} / {op['edge']}",
            "",
            "Przed: obiekt nie istnieje. Po:",
            "",
            "```json",
            json.dumps(op["params"], ensure_ascii=False, indent=2),
            "```",
        ]
    return "\n".join(lines) + "\n"
