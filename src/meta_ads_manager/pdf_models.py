"""Portable, presentation-only contracts. No markup, remote assets or executable content."""

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, model_validator

from meta_ads_manager.models import Identifier, Model

Text = Annotated[str, Field(min_length=1, max_length=20000)]
Short = Annotated[str, Field(min_length=1, max_length=300)]


class PdfTable(Model):
    columns: list[Short] = Field(min_length=1, max_length=6)
    rows: list[list[str]] = Field(max_length=10000)
    widths: list[float] | None = None
    numeric_columns: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def shape(self):
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("Table rows must match columns")
        if self.widths is not None and (
            len(self.widths) != len(self.columns)
            or any(not 0 < width <= 100 for width in self.widths)
        ):
            raise ValueError("Invalid relative column widths")
        if any(index < 0 or index >= len(self.columns) for index in self.numeric_columns):
            raise ValueError("Invalid numeric column")
        if any(len(cell) > 20000 for row in self.rows for cell in row):
            raise ValueError("Table cell too long")
        return self


class PdfSection(Model):
    title: Short
    paragraphs: list[Text] = Field(default_factory=list)
    bullets: list[Text] = Field(default_factory=list)
    table: PdfTable | None = None
    new_page: bool = False


class PdfMetric(Model):
    label: Short
    value: Short
    detail: Short | None = None


class PdfDocument(Model):
    schema_version: Literal["1.0"] = "1.0"
    kind: Literal["pdf_document"] = "pdf_document"
    client_id: Identifier
    account_id: Identifier
    title: Short
    subtitle: Short | None = None
    source: Literal["meta", "demo", "manual"]
    report_date: date
    period_since: date
    period_until: date
    currency: str | None = None
    timezone: str | None = None
    coverage: Literal["partial", "report", "custom"]
    summary: list[Text] = Field(default_factory=list)
    metrics: list[PdfMetric] = Field(default_factory=list, max_length=12)
    sections: list[PdfSection] = Field(default_factory=list, max_length=100)
    limitations: list[Text] = Field(min_length=1)
    evidence: list[Text] = Field(min_length=1)

    @model_validator(mode="after")
    def dates(self):
        if self.period_since > self.period_until:
            raise ValueError("Reversed period")
        return self


class PdfNotes(Model):
    schema_version: Literal["1.0"] = "1.0"
    kind: Literal["pdf_notes"] = "pdf_notes"
    client_id: Identifier
    account_id: Identifier
    report_id: Identifier
    snapshot_id: Identifier
    knowledge_version: Short | None = None
    rule_ids: list[Short] = Field(default_factory=list)
    sections: list[PdfSection] = Field(min_length=1, max_length=30)
