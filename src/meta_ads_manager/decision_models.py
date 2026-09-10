"""Explicit business definitions and local recommendation history contracts."""

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, model_validator

from meta_ads_manager.models import (
    Contract,
    Currency,
    Identifier,
    Model,
    Nonempty,
    Number,
    PositiveNumber,
)

Revision = Annotated[int, Field(ge=1)]
Expected = Annotated[int, Field(ge=0)]


class Scope(Contract):
    client_id: Identifier
    account_id: Identifier


class ResultTargets(Model):
    cost_per_result: PositiveNumber | None = None
    roas: PositiveNumber | None = None


class BusinessGoal(Scope):
    kind: Literal["business_goal"]
    goal_id: Identifier
    expected_revision: Expected
    project_id: Identifier
    name: Nonempty
    business_outcome: Nonempty
    result_label: Nonempty
    result_type: Literal["lead", "purchase", "registration", "outbound_click", "custom"]
    measurement_role: Literal["primary", "proxy", "diagnostic"]
    conversion_location: Literal["meta_instant_form", "website", "other"]
    action_type: Identifier
    value_action_type: Identifier | None = None
    currency: Currency
    attribution: Literal["7d_click_1d_view"] = "7d_click_1d_view"
    action_report_time: Literal["impression"] = "impression"
    missing_action_policy: Literal["unknown", "zero_when_omitted"] = "unknown"
    targets: ResultTargets
    confirmed_by: Nonempty
    confirmation_ref: Nonempty

    @model_validator(mode="after")
    def revenue(self):
        if self.value_action_type is not None and (
            self.result_type != "purchase"
            or self.measurement_role != "primary"
            or self.value_action_type != self.action_type
        ):
            raise ValueError("Value requires the same primary purchase action")
        if self.targets.roas is not None and self.value_action_type is None:
            raise ValueError("ROAS requires purchase value mapping")
        return self


class CampaignGoalAssignment(Scope):
    kind: Literal["campaign_goal_assignment"]
    campaign_id: Identifier
    goal_id: Identifier | None
    goal_revision: Revision | None
    effective_from: date
    expected_revision: Expected
    confirmed_by: Nonempty
    confirmation_ref: Nonempty

    @model_validator(mode="after")
    def reference_pair(self):
        if (self.goal_id is None) != (self.goal_revision is None):
            raise ValueError("Goal and revision must be supplied together")
        return self


class Window(Model):
    since: date
    until: date

    @model_validator(mode="after")
    def ordered(self):
        if self.since > self.until:
            raise ValueError("Reversed window")
        return self


class TestPlan(Model):
    hypothesis: Nonempty
    method: Literal["before_after", "observation"]
    baseline: Window
    evaluation_days: Annotated[int, Field(ge=1, le=90)]
    metric: Literal["cost_per_result", "roas", "results"]
    direction: Literal["increase", "decrease"]
    success_threshold: PositiveNumber | None = None
    minimum_results: Number | None = None
    stop_condition: Nonempty

    @model_validator(mode="after")
    def compatible(self):
        if (self.baseline.until - self.baseline.since).days + 1 != self.evaluation_days:
            raise ValueError("Use equally long comparison windows")
        if self.metric == "cost_per_result" and self.direction != "decrease":
            raise ValueError("Cost criterion must decrease")
        if self.metric in ("roas", "results") and self.direction != "increase":
            raise ValueError("Result criterion must increase")
        return self


class Recommendation(Scope):
    kind: Literal["recommendation"]
    recommendation_id: Identifier
    goal_id: Identifier
    goal_revision: Revision
    campaign_ids: list[Identifier] = Field(min_length=1)
    title: Nonempty
    action: Nonempty
    rationale: Nonempty
    priority: Literal["high", "medium", "low"]
    evidence_refs: list[Nonempty] = Field(min_length=1)
    test_plan: TestPlan
    followup_of: Identifier | None = None
    followup_reason: Nonempty | None = None

    @model_validator(mode="after")
    def unique_campaigns(self):
        if len(set(self.campaign_ids)) != len(self.campaign_ids):
            raise ValueError("Repeated campaign")
        if (self.followup_of is None) != (self.followup_reason is None):
            raise ValueError("A follow-up requires both reference and reason")
        if self.followup_of == self.recommendation_id:
            raise ValueError("A recommendation cannot follow itself")
        return self


class RecommendationEvent(Scope):
    kind: Literal["recommendation_event"]
    event_id: Identifier
    recommendation_id: Identifier
    expected_revision: Revision
    event: Literal["accept", "reject", "defer", "start", "cancel", "note"]
    actor: Nonempty
    reason: Nonempty
    evidence_refs: list[Nonempty] = Field(min_length=1)
    effective_on: date | None = None
    review_on: date | None = None

    @model_validator(mode="after")
    def dates(self):
        if (self.event == "start") != (self.effective_on is not None):
            raise ValueError("Only start requires effective_on")
        if (self.event == "defer") != (self.review_on is not None):
            raise ValueError("Only defer requires review_on")
        return self


DECISION_CONTRACTS = {
    "business_goal": BusinessGoal,
    "campaign_goal_assignment": CampaignGoalAssignment,
    "recommendation": Recommendation,
    "recommendation_event": RecommendationEvent,
}
