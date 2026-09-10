"""Versioned contracts shared by the CLI, providers and storage."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator


def decimal_input(value: object) -> Decimal:
    # Floats and JSON numbers are deliberately rejected at the public boundary.
    if not isinstance(value, (str, Decimal)):
        raise ValueError("Decimal values must be strings")
    try:
        result = Decimal(value)
    except ArithmeticError as exc:
        raise ValueError("Invalid decimal") from exc
    if not result.is_finite():
        raise ValueError("Decimal must be finite")
    return result


Number = Annotated[
    Decimal,
    BeforeValidator(decimal_input, json_schema_input_type=str),
    Field(ge=0, max_digits=20, decimal_places=6),
]
PositiveNumber = Annotated[Number, Field(gt=0)]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
Nonempty = Annotated[str, Field(min_length=1, max_length=2000)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_default=True)


class Contract(Model):
    schema_version: Literal["1.0"]


class Account(Model):
    account_id: Identifier
    credential_ref: Annotated[str, Field(pattern=r"^(env:[A-Z][A-Z0-9_]*|local:[a-z0-9-]+)$")]
    currency: Currency
    timezone: str

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown timezone") from exc
        return value


class LeadTargets(Model):
    cpl: PositiveNumber | None = None


class CommerceTargets(Model):
    cpa: PositiveNumber | None = None
    roas: PositiveNumber | None = None


class LeadGoal(Model):
    goal_id: Identifier
    type: Literal["lead_generation"]
    primary_outcome: Literal["lead"]
    target_metrics: LeadTargets
    crm_source_ref: Identifier | None = None


class CommerceGoal(Model):
    goal_id: Identifier
    type: Literal["ecommerce"]
    primary_outcome: Literal["purchase"]
    target_metrics: CommerceTargets
    commerce_source_ref: Identifier | None = None


Goal = Annotated[LeadGoal | CommerceGoal, Field(discriminator="type")]


class Project(Model):
    project_id: Identifier
    account_ids: list[Identifier] = Field(min_length=1)
    market: Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
    goal_profiles: list[Goal] = Field(min_length=1)


class Policy(Model):
    version: Identifier
    # Only read-only policies are implemented in this release.
    mode: Literal["analyst"]
    allowed_write_operations: list[str] = Field(max_length=0)
    automation_enabled: Literal[False]


class ClientProfile(Contract):
    kind: Literal["client_profile"]
    client_id: Identifier
    name: Nonempty
    accounts: list[Account] = Field(min_length=1)
    projects: list[Project]
    policy: Policy

    @model_validator(mode="after")
    def references(self):
        accounts = [a.account_id for a in self.accounts]
        projects = [p.project_id for p in self.projects]
        goals = [g.goal_id for p in self.projects for g in p.goal_profiles]
        for identifiers in (accounts, projects, goals):
            if len(set(identifiers)) != len(identifiers):
                raise ValueError("Duplicate identifiers")
        for project in self.projects:
            if len(set(project.account_ids)) != len(project.account_ids):
                raise ValueError("Duplicate project account")
            if not set(project.account_ids).issubset(accounts):
                raise ValueError("Project refers to an unknown account")
        return self


class Budget(Model):
    level: Literal["campaign", "adset"]
    period: Literal["daily", "lifetime"]
    amount: PositiveNumber
    currency: Currency


class Assets(Model):
    page_id: Identifier | None = None
    instagram_actor_id: Identifier | None = None
    lead_form_id: Identifier | None = None
    event_source_id: Identifier | None = None
    optimization_event: Literal["purchase", "lead"] | None = None
    landing_page_url: Annotated[str, Field(pattern=r"^https://[^\s]+$")] | None = None
    creative_asset_ids: list[Identifier]


class CampaignBrief(Contract):
    kind: Literal["campaign_brief"]
    client_id: Identifier
    account_id: Identifier
    project_id: Identifier
    goal_id: Identifier
    name: Nonempty
    conversion_location: Literal["meta_instant_form", "website"]
    market: Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
    language: Annotated[str, Field(pattern=r"^[a-z]{2}$")]
    budget: Budget
    initial_status: Literal["PAUSED"]
    offer: Nonempty
    asset_refs: Assets
    special_ad_categories: list[Nonempty] | None
    missing_requirements: list[Nonempty]


class BudgetState(Model):
    budget_level: Literal["campaign", "adset"]
    budget_period: Literal["daily", "lifetime"]
    amount: PositiveNumber
    currency: Currency


class BudgetOperation(Model):
    operation_id: Identifier
    type: Literal["set_budget"]
    object_type: Literal["campaign", "adset"]
    object_id: Identifier
    expected: BudgetState
    desired: BudgetState

    @model_validator(mode="after")
    def compatible_budget(self):
        if self.expected.currency != self.desired.currency:
            raise ValueError("Cannot change budget currency")
        if self.expected.budget_period != self.desired.budget_period:
            raise ValueError("Cannot change budget period with set_budget")
        if any(s.budget_level != self.object_type for s in (self.expected, self.desired)):
            raise ValueError("Budget level must match object type")
        return self


class ChangeProposal(Contract):
    kind: Literal["change_proposal"]
    client_id: Identifier
    account_id: Identifier
    goal_id: Identifier
    operations: list[BudgetOperation] = Field(min_length=1)
    rationale: Nonempty
    evidence_refs: list[Identifier]
    missing_requirements: list[Nonempty]

    @model_validator(mode="after")
    def unique_operations(self):
        ids = [op.operation_id for op in self.operations]
        objects = [(op.object_type, op.object_id) for op in self.operations]
        if len(set(ids)) != len(ids) or len(set(objects)) != len(objects):
            raise ValueError("Duplicate operation or target")
        return self


class ReportSpec(Model):
    level: Literal["campaign"]
    currency: Currency
    timezone: str
    click_type: Literal["link_click"]
    attribution: Literal["demo_7d_click_1d_view", "7d_click_1d_view"]
    action_report_time: Literal["impression"]
    api_version: Annotated[str, Field(pattern=r"^(demo-no-api|v[0-9]+\.[0-9]+)$")]
    normalization_version: Literal["1"]

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        return Account.known_timezone(value)


class Campaign(Model):
    campaign_id: Identifier
    goal_id: Identifier | None
    name: Nonempty
    status: Nonempty
    objective: Nonempty | None = None


class Fact(Model):
    campaign_id: Identifier
    day: date
    spend: Number
    impressions: Annotated[int, Field(ge=0)]
    link_clicks: Annotated[int, Field(ge=0)]
    conversions: Number | None
    conversion_value: Number | None
    actions: dict[str, Number] = Field(default_factory=dict)
    action_values: dict[str, Number] = Field(default_factory=dict)
    inferred_no_delivery: bool = False


class MetaEvidence(Model):
    account_name: Nonempty
    inventory_count: Annotated[int, Field(ge=0)]
    insight_row_count: Annotated[int, Field(ge=0)]
    account_spend: Number
    account_impressions: Annotated[int, Field(ge=0)]
    account_link_clicks: Annotated[int, Field(ge=0)]
    reconciliation: Literal["matched"]


class Snapshot(Contract):
    kind: Literal["snapshot"]
    client_id: Identifier
    account_id: Identifier
    source: Literal["demo", "meta"]
    since: date
    until: date
    fetched_at: datetime
    complete: Literal[True]
    spec: ReportSpec
    campaigns: list[Campaign]
    facts: list[Fact]
    meta: MetaEvidence | None = None

    @model_validator(mode="after")
    def complete_period(self):
        if self.source == "meta":
            if self.meta is None or self.spec.api_version == "demo-no-api":
                raise ValueError("Missing Meta provenance")
            if self.spec.attribution != "7d_click_1d_view":
                raise ValueError("Invalid Meta attribution")
        elif self.meta is not None or self.spec.api_version != "demo-no-api":
            raise ValueError("Invalid demo provenance")
        if self.since > self.until:
            raise ValueError("Reversed report period")
        if self.fetched_at.tzinfo is None:
            raise ValueError("Timestamp must have a timezone")
        if self.until >= self.fetched_at.astimezone(ZoneInfo(self.spec.timezone)).date():
            raise ValueError("Report includes an unfinished day")
        ids = {c.campaign_id for c in self.campaigns}
        if len(ids) != len(self.campaigns):
            raise ValueError("Duplicate campaign")
        keys = {(f.campaign_id, f.day) for f in self.facts}
        expected_count = len(ids) * ((self.until - self.since).days + 1)
        if len(keys) != len(self.facts) or len(keys) != expected_count:
            raise ValueError("Incomplete or duplicate facts")
        if any(
            f.campaign_id not in ids or not self.since <= f.day <= self.until for f in self.facts
        ):
            raise ValueError("Fact outside report scope")
        return self


class DemoDataset(Contract):
    kind: Literal["demo_dataset"]
    profiles: list[ClientProfile] = Field(min_length=1)
    snapshots: list[Snapshot] = Field(min_length=1)

    @model_validator(mode="after")
    def scoped_snapshots(self):
        clients = [p.client_id for p in self.profiles]
        all_accounts = [a.account_id for p in self.profiles for a in p.accounts]
        if len(set(clients)) != len(clients) or len(set(all_accounts)) != len(all_accounts):
            raise ValueError("Duplicate client or account owner")
        scopes = [(s.client_id, s.account_id) for s in self.snapshots]
        if len(set(scopes)) != len(scopes):
            raise ValueError("Duplicate snapshot scope")
        for snapshot in self.snapshots:
            profile = next((p for p in self.profiles if p.client_id == snapshot.client_id), None)
            account = (
                next((a for a in profile.accounts if a.account_id == snapshot.account_id), None)
                if profile
                else None
            )
            if account is None:
                raise ValueError("Snapshot outside client account scope")
            if (account.currency, account.timezone) != (
                snapshot.spec.currency,
                snapshot.spec.timezone,
            ):
                raise ValueError("Snapshot account settings mismatch")
            goals = {
                g.goal_id
                for p in profile.projects
                if snapshot.account_id in p.account_ids
                for g in p.goal_profiles
            }
            if any(c.goal_id not in goals for c in snapshot.campaigns):
                raise ValueError("Campaign goal outside account scope")
        return self


CONTRACTS = {
    "client_profile": ClientProfile,
    "campaign_brief": CampaignBrief,
    "change_proposal": ChangeProposal,
    "snapshot": Snapshot,
    "demo_dataset": DemoDataset,
}
