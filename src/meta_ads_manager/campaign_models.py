"""Typed conversational intake and bounded campaign creation contracts."""

import ipaddress
from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator, model_validator

from meta_ads_manager.models import Contract, Identifier, Model, Nonempty, PositiveNumber

MetaId = Annotated[str, Field(pattern=r"^[0-9]+$")]
Code = Annotated[str, Field(min_length=1, max_length=32)]


class AdInput(Model):
    concept: Code
    image_hash: Annotated[str, Field(pattern=r"^[a-fA-F0-9]{32}$")]
    message: Annotated[str, Field(min_length=1, max_length=2000)]
    headline: Annotated[str, Field(min_length=1, max_length=100)]
    description: Annotated[str, Field(max_length=200)] = ""
    cta: Literal["LEARN_MORE", "SIGN_UP", "SHOP_NOW", "GET_QUOTE", "BOOK_TRAVEL"]
    version: Annotated[int, Field(ge=1, le=999)] = 1


class AdSetInput(Model):
    audience_code: Literal["BROAD"]
    countries: list[Annotated[str, Field(pattern=r"^[A-Z]{2}$")]] = Field(
        min_length=1, max_length=10
    )
    age_min: Annotated[int, Field(ge=18, le=65)]
    age_max: Annotated[int, Field(ge=18, le=65)]
    budget: PositiveNumber
    ads: list[AdInput] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def ages(self):
        if self.age_min > self.age_max or len(set(self.countries)) != len(self.countries):
            raise ValueError("Invalid audience")
        return self


class CreationBrief(Contract):
    kind: Literal["creation_brief"]
    client_id: Identifier
    account_id: Annotated[str, Field(pattern=r"^act_[0-9]+$")]
    project_id: Identifier
    client_code: Code
    project_code: Code
    goal_id: Identifier
    goal_revision: Annotated[int, Field(ge=1)]
    goal_kind: Literal["leads", "sales", "registrations", "tickets"]
    offer: Nonempty
    result_definition: Nonempty
    measurement: Literal["lead_form", "web_lead", "purchase", "registration", "custom_proxy"]
    language: Annotated[str, Field(pattern=r"^[a-z]{2}$")]
    role: Literal["MAIN", "TEST"]
    currency: Literal["PLN", "EUR", "USD", "GBP"]
    timezone: str
    budget_period: Literal["daily", "lifetime"]
    start_time: datetime
    end_time: datetime
    landing_url: str
    page_id: MetaId
    lead_form_id: MetaId | None = None
    pixel_id: MetaId | None = None
    custom_conversion_id: MetaId | None = None
    special_ad_categories: list[str] = Field(max_length=0)
    dsa_beneficiary: Nonempty
    dsa_payor: Nonempty
    placements: Literal["facebook_feed"]
    adsets: list[AdSetInput] = Field(min_length=1, max_length=5)
    followup_process: Nonempty
    test_hypothesis: Nonempty
    test_success: Nonempty
    test_review: Nonempty
    stop_condition: Nonempty
    rights_confirmed: Literal[True]
    measurement_confirmed: Literal[True]

    @field_validator("landing_url")
    @classmethod
    def public_url(cls, value):
        p = urlsplit(value)
        if (
            p.scheme != "https"
            or not p.hostname
            or p.username
            or p.password
            or p.port not in (None, 443)
            or any(c.isspace() for c in value)
        ):
            raise ValueError("Use a public HTTPS landing URL")
        try:
            address = ipaddress.ip_address(p.hostname)
        except ValueError:
            if p.hostname in ("localhost", "localhost.localdomain"):
                raise ValueError("Local landing URL") from None
        else:
            if not address.is_global:
                raise ValueError("Private landing URL")
        return value

    @field_validator("timezone")
    @classmethod
    def zone(cls, value):
        ZoneInfo(value)
        return value

    @model_validator(mode="after")
    def consistency(self):
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("Schedule requires timezone offsets")
        if self.end_time <= self.start_time:
            raise ValueError("Invalid schedule")
        for dt in (self.start_time, self.end_time):
            if dt.utcoffset() != dt.astimezone(ZoneInfo(self.timezone)).utcoffset():
                raise ValueError("Schedule offset differs from account timezone")
        combinations = {
            "leads": {"lead_form", "web_lead"},
            "sales": {"purchase"},
            "registrations": {"registration", "lead_form"},
            "tickets": {"purchase", "custom_proxy"},
        }
        if self.measurement not in combinations[self.goal_kind]:
            raise ValueError("Business goal and measurement differ")
        if self.measurement == "lead_form":
            if not self.lead_form_id or self.pixel_id or self.custom_conversion_id:
                raise ValueError("Lead form requires only a form ID")
        elif not self.pixel_id or self.lead_form_id:
            raise ValueError("Website measurement requires a pixel and no form")
        if (self.measurement == "custom_proxy") != bool(self.custom_conversion_id):
            raise ValueError("Proxy requires a custom conversion")
        for adset in self.adsets:
            if adset.budget * 100 != (adset.budget * 100).to_integral_value():
                raise ValueError("Budget accepts at most two decimal places")
            if self.measurement == "lead_form" and any(
                a.cta not in ("SIGN_UP", "GET_QUOTE", "LEARN_MORE") for a in adset.ads
            ):
                raise ValueError("Unsupported lead form CTA")
        return self


class FieldAnswer(Model):
    value: object
    state: Literal["discovered", "confirmed", "conflict", "unavailable"]
    source: Literal["operator", "website", "context", "api", "agent"]
    evidence_ref: Nonempty

    @model_validator(mode="after")
    def confirmation(self):
        if self.state == "confirmed" and self.source not in ("operator", "api"):
            raise ValueError("Only an operator or technical API fact can confirm a field")
        return self


class WizardAnswer(Contract):
    kind: Literal["wizard_answer"]
    client_id: Identifier
    account_id: Annotated[str, Field(pattern=r"^act_[0-9]+$")]
    draft_id: Identifier
    expected_revision: Annotated[int, Field(ge=1)]
    fields: dict[str, FieldAnswer] = Field(min_length=1)


CAMPAIGN_CONTRACTS = {"creation_brief": CreationBrief, "wizard_answer": WizardAnswer}


class WizardApproval(Contract):
    kind: Literal["wizard_approval"]
    client_id: Identifier
    account_id: Annotated[str, Field(pattern=r"^act_[0-9]+$")]
    plan_hash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    approval_id: Identifier
    expected_revision: Annotated[int, Field(ge=0)]
    decision: Literal["approve", "revoke"]
    operator_name: Nonempty
    operator_message: Annotated[str, Field(min_length=10, max_length=4000)]
    evidence_ref: Nonempty


CAMPAIGN_CONTRACTS["wizard_approval"] = WizardApproval
