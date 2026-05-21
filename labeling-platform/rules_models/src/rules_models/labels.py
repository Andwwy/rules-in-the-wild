from __future__ import annotations

from pydantic import BaseModel, Field

from rules_models.core import (
    AmbiguityLevel,
    ClassificationPrediction,
    Decision,
    DocumentItem,
    SourceLine,
)


class ExtractionLabelIn(BaseModel):
    decision: Decision
    corrected_rule_text: str | None = None
    corrected_start_line: int | None = None
    corrected_end_line: int | None = None
    notes: str = ""


class MissingExtractionLabelIn(BaseModel):
    document_id: str
    source_path: str
    rule_text: str
    start_line: int
    end_line: int
    notes: str = ""


class ExtractionLabel(BaseModel):
    target_key: str
    decision: Decision
    corrected_rule_text: str | None
    corrected_start_line: int | None
    corrected_end_line: int | None
    notes: str
    is_missing: bool


class ExtractionItem(BaseModel):
    target_key: str
    document_id: str
    source_path: str
    rule_id: str | None
    rule_text: str
    start_line: int
    end_line: int
    source_lines: list[SourceLine]
    label: ExtractionLabel | None


class ClassificationLabelIn(BaseModel):
    decision: Decision
    corrected_prerequisites: list[str] = Field(default_factory=list)
    corrected_enforcement_mechanisms: list[str] = Field(default_factory=list)
    corrected_triggers: list[str] = Field(default_factory=list)
    corrected_ambiguity_level: AmbiguityLevel | None = None
    corrected_ambiguity_notes: str = ""
    notes: str = ""


class ClassificationLabel(BaseModel):
    target_key: str
    decision: Decision
    corrected_prerequisites: list[str]
    corrected_enforcement_mechanisms: list[str]
    corrected_triggers: list[str]
    corrected_ambiguity_level: AmbiguityLevel | None
    corrected_ambiguity_notes: str
    notes: str


class ClassificationItem(BaseModel):
    target_key: str
    document_id: str
    source_path: str
    rule_id: str | None
    rule_text: str
    start_line: int
    end_line: int
    source_lines: list[SourceLine]
    prediction: ClassificationPrediction | None
    label: ClassificationLabel | None


class Stats(BaseModel):
    documents: int
    extraction_items: int
    extraction_labels: int
    classification_items: int
    classification_labels: int


__all__ = [
    "ClassificationItem",
    "ClassificationLabel",
    "ClassificationLabelIn",
    "ClassificationPrediction",
    "DocumentItem",
    "ExtractionItem",
    "ExtractionLabel",
    "ExtractionLabelIn",
    "MissingExtractionLabelIn",
    "SourceLine",
    "Stats",
]
