from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


Decision = Literal["accept", "correct", "reject", "skip"]
AmbiguityLevel = Literal["none", "low", "medium", "high"]


class SourceDocument(BaseModel):
    document_id: str
    source_path: str
    document_name: str
    document_text: str
    content_sha256: str
    ingested_at: datetime | None = None


class DocumentItem(BaseModel):
    document_id: str
    source_path: str
    document_name: str


class SourceLine(BaseModel):
    line_number: int
    text: str


class ExtractedRule(BaseModel):
    rule_id: str
    document_id: str
    source_path: str
    rule_index: int
    rule_text: str
    start_line: int
    end_line: int
    extracted_at: datetime | None = None


class ClassifiedRule(BaseModel):
    rule_id: str
    document_id: str
    source_path: str
    rule_text: str
    prerequisites: list[str]
    enforcement_mechanisms: list[str]
    triggers: list[str]
    ambiguity_level: AmbiguityLevel | str
    ambiguity_notes: str
    confidence: float
    classified_at: datetime | None = None


class ClassificationPrediction(BaseModel):
    prerequisites: list[str]
    enforcement_mechanisms: list[str]
    triggers: list[str]
    ambiguity_level: AmbiguityLevel | str
    ambiguity_notes: str
    confidence: float


class PipelineStats(BaseModel):
    documents: int
    extracted_rules: int
    classified_rules: int
