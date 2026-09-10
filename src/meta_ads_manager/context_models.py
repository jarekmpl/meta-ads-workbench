"""Grounded client context; dates describe applicability, never implicit precedence."""

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, model_validator

from meta_ads_manager.models import Contract, Identifier, Model, Nonempty

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ContextReference(Model):
    client_id: Identifier
    material_id: Identifier
    sha256: Digest
    chunk_id: Digest
    locator: Nonempty
    title: Nonempty
    quote: Annotated[str, Field(min_length=1, max_length=2400)]


class ContextRule(Contract):
    kind: Literal["context_rule"]
    client_id: Identifier
    rule_id: Identifier
    key: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{0,127}$")]
    value: Nonempty
    project: Nonempty | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    sources: list[ContextReference] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def bounds(self):
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            raise ValueError("Reversed validity dates")
        if any(ref.client_id != self.client_id for ref in self.sources):
            raise ValueError("Mixed clients")
        return self


class ContextBasis(Model):
    client_id: Identifier
    project: Nonempty | None = None
    as_of: date
    rule_ids: list[Identifier] = Field(min_length=1, max_length=50)
    rules: list[ContextRule] = Field(min_length=1, max_length=50)
    sources: list[ContextReference] = Field(min_length=1, max_length=100)
    used_for: Nonempty

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.rule_ids)) != len(self.rule_ids):
            raise ValueError("Repeated rule")
        if any(ref.client_id != self.client_id for ref in self.sources):
            raise ValueError("Mixed clients")
        if sorted(rule.rule_id for rule in self.rules) != sorted(self.rule_ids):
            raise ValueError("Rule snapshots do not match identifiers")
        if any(rule.client_id != self.client_id for rule in self.rules):
            raise ValueError("Mixed clients")
        return self
