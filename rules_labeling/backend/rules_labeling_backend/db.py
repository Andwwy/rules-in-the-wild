from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import duckdb

from rules_labeling_backend.keys import extraction_target_key, snapshot_hash
from rules_labeling_backend.models import (
    ClassificationItem,
    ClassificationLabel,
    ClassificationLabelIn,
    ClassificationPrediction,
    DocumentItem,
    ExtractionItem,
    ExtractionLabel,
    ExtractionLabelIn,
    MissingExtractionLabelIn,
    SourceLine,
    Stats,
)

Status = Literal["all", "unlabeled", "labeled"]


LABEL_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS extraction_labels (
    target_key VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL,
    source_path VARCHAR NOT NULL,
    predicted_rule_id VARCHAR,
    predicted_rule_text VARCHAR,
    predicted_start_line INTEGER,
    predicted_end_line INTEGER,
    decision VARCHAR NOT NULL,
    corrected_rule_text VARCHAR,
    corrected_start_line INTEGER,
    corrected_end_line INTEGER,
    notes VARCHAR NOT NULL DEFAULT '',
    is_missing BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS classification_labels (
    target_key VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL,
    source_path VARCHAR NOT NULL,
    predicted_rule_id VARCHAR,
    predicted_rule_text VARCHAR NOT NULL,
    predicted_start_line INTEGER NOT NULL,
    predicted_end_line INTEGER NOT NULL,
    predicted_snapshot_hash VARCHAR NOT NULL,
    predicted_prerequisites JSON,
    predicted_enforcement_mechanisms JSON,
    predicted_triggers JSON,
    predicted_ambiguity_level VARCHAR,
    predicted_ambiguity_notes VARCHAR,
    predicted_confidence DOUBLE,
    decision VARCHAR NOT NULL,
    corrected_prerequisites JSON NOT NULL,
    corrected_enforcement_mechanisms JSON NOT NULL,
    corrected_triggers JSON NOT NULL,
    corrected_ambiguity_level VARCHAR,
    corrected_ambiguity_notes VARCHAR NOT NULL DEFAULT '',
    notes VARCHAR NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);
"""


class LabelStore:
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.con = duckdb.connect(str(db_path))
        self.con.execute("LOAD json;")
        self.ensure_label_schema()

    def ensure_label_schema(self) -> None:
        self.con.execute(LABEL_SCHEMA_SQL)

    def documents(self) -> list[DocumentItem]:
        rows = self.con.execute(
            """
            SELECT document_id, source_path, document_name
            FROM source_documents
            ORDER BY document_name, source_path
            """
        ).fetchall()
        return [
            DocumentItem(document_id=row[0], source_path=row[1], document_name=row[2])
            for row in rows
        ]

    def extraction_items(self, status: Status = "all") -> list[ExtractionItem]:
        items = self._predicted_extraction_items()
        items.extend(self._missing_extraction_items())
        items.sort(key=lambda item: (item.source_path, item.start_line, item.rule_text))
        return self._filter_by_status(items, status)

    def upsert_extraction_label(
        self,
        target_key: str,
        payload: ExtractionLabelIn,
    ) -> ExtractionLabel:
        item = self._find_extraction_item(target_key)
        corrected_rule_text = payload.corrected_rule_text
        corrected_start_line = payload.corrected_start_line
        corrected_end_line = payload.corrected_end_line
        self.con.execute(
            """
            INSERT INTO extraction_labels (
                target_key,
                document_id,
                source_path,
                predicted_rule_id,
                predicted_rule_text,
                predicted_start_line,
                predicted_end_line,
                decision,
                corrected_rule_text,
                corrected_start_line,
                corrected_end_line,
                notes,
                is_missing,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, false, now())
            ON CONFLICT (target_key) DO UPDATE SET
                predicted_rule_id = excluded.predicted_rule_id,
                predicted_rule_text = excluded.predicted_rule_text,
                predicted_start_line = excluded.predicted_start_line,
                predicted_end_line = excluded.predicted_end_line,
                decision = excluded.decision,
                corrected_rule_text = excluded.corrected_rule_text,
                corrected_start_line = excluded.corrected_start_line,
                corrected_end_line = excluded.corrected_end_line,
                notes = excluded.notes,
                is_missing = false,
                updated_at = now()
            """,
            [
                target_key,
                item.document_id,
                item.source_path,
                item.rule_id,
                item.rule_text,
                item.start_line,
                item.end_line,
                payload.decision,
                corrected_rule_text,
                corrected_start_line,
                corrected_end_line,
                payload.notes,
            ],
        )
        return self._get_extraction_label(target_key)

    def add_missing_extraction_label(
        self,
        payload: MissingExtractionLabelIn,
    ) -> ExtractionLabel:
        target_key = extraction_target_key(
            document_id=payload.document_id,
            start_line=payload.start_line,
            end_line=payload.end_line,
            rule_text=payload.rule_text,
        )
        self.con.execute(
            """
            INSERT INTO extraction_labels (
                target_key,
                document_id,
                source_path,
                predicted_rule_id,
                predicted_rule_text,
                predicted_start_line,
                predicted_end_line,
                decision,
                corrected_rule_text,
                corrected_start_line,
                corrected_end_line,
                notes,
                is_missing,
                updated_at
            )
            VALUES (?, ?, ?, NULL, NULL, NULL, NULL, 'correct', ?, ?, ?, ?, true, now())
            ON CONFLICT (target_key) DO UPDATE SET
                decision = 'correct',
                corrected_rule_text = excluded.corrected_rule_text,
                corrected_start_line = excluded.corrected_start_line,
                corrected_end_line = excluded.corrected_end_line,
                notes = excluded.notes,
                is_missing = true,
                updated_at = now()
            """,
            [
                target_key,
                payload.document_id,
                payload.source_path,
                payload.rule_text,
                payload.start_line,
                payload.end_line,
                payload.notes,
            ],
        )
        return self._get_extraction_label(target_key)

    def classification_items(self, status: Status = "all") -> list[ClassificationItem]:
        extraction_items = [
            item
            for item in self.extraction_items("all")
            if item.label is None or item.label.decision != "reject"
        ]
        labels = self._classification_labels()
        predictions = self._classification_predictions()
        items = []
        for extraction in extraction_items:
            label = labels.get(extraction.target_key)
            prediction = predictions.get(extraction.rule_id or "")
            rule_text = extraction.rule_text
            start_line = extraction.start_line
            end_line = extraction.end_line
            if extraction.label and extraction.label.decision == "correct":
                rule_text = extraction.label.corrected_rule_text or rule_text
                start_line = extraction.label.corrected_start_line or start_line
                end_line = extraction.label.corrected_end_line or end_line
            items.append(
                ClassificationItem(
                    target_key=extraction.target_key,
                    document_id=extraction.document_id,
                    source_path=extraction.source_path,
                    rule_id=extraction.rule_id,
                    rule_text=rule_text,
                    start_line=start_line,
                    end_line=end_line,
                    source_lines=extraction.source_lines,
                    prediction=prediction,
                    label=label,
                )
            )
        return self._filter_by_status(items, status)

    def upsert_classification_label(
        self,
        target_key: str,
        payload: ClassificationLabelIn,
    ) -> ClassificationLabel:
        item = self._find_classification_item(target_key)
        prediction = item.prediction or ClassificationPrediction(
            prerequisites=[],
            enforcement_mechanisms=[],
            triggers=[],
            ambiguity_level="",
            ambiguity_notes="",
            confidence=0.0,
        )
        snapshot = json.dumps(prediction.model_dump(), sort_keys=True)
        self.con.execute(
            """
            INSERT INTO classification_labels (
                target_key,
                document_id,
                source_path,
                predicted_rule_id,
                predicted_rule_text,
                predicted_start_line,
                predicted_end_line,
                predicted_snapshot_hash,
                predicted_prerequisites,
                predicted_enforcement_mechanisms,
                predicted_triggers,
                predicted_ambiguity_level,
                predicted_ambiguity_notes,
                predicted_confidence,
                decision,
                corrected_prerequisites,
                corrected_enforcement_mechanisms,
                corrected_triggers,
                corrected_ambiguity_level,
                corrected_ambiguity_notes,
                notes,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?::JSON, ?::JSON, ?::JSON, ?, ?, ?, ?,
                ?::JSON, ?::JSON, ?::JSON, ?, ?, ?, now()
            )
            ON CONFLICT (target_key) DO UPDATE SET
                predicted_rule_id = excluded.predicted_rule_id,
                predicted_rule_text = excluded.predicted_rule_text,
                predicted_start_line = excluded.predicted_start_line,
                predicted_end_line = excluded.predicted_end_line,
                predicted_snapshot_hash = excluded.predicted_snapshot_hash,
                predicted_prerequisites = excluded.predicted_prerequisites,
                predicted_enforcement_mechanisms = excluded.predicted_enforcement_mechanisms,
                predicted_triggers = excluded.predicted_triggers,
                predicted_ambiguity_level = excluded.predicted_ambiguity_level,
                predicted_ambiguity_notes = excluded.predicted_ambiguity_notes,
                predicted_confidence = excluded.predicted_confidence,
                decision = excluded.decision,
                corrected_prerequisites = excluded.corrected_prerequisites,
                corrected_enforcement_mechanisms = excluded.corrected_enforcement_mechanisms,
                corrected_triggers = excluded.corrected_triggers,
                corrected_ambiguity_level = excluded.corrected_ambiguity_level,
                corrected_ambiguity_notes = excluded.corrected_ambiguity_notes,
                notes = excluded.notes,
                updated_at = now()
            """,
            [
                target_key,
                item.document_id,
                item.source_path,
                item.rule_id,
                item.rule_text,
                item.start_line,
                item.end_line,
                snapshot_hash(snapshot),
                json.dumps(prediction.prerequisites),
                json.dumps(prediction.enforcement_mechanisms),
                json.dumps(prediction.triggers),
                prediction.ambiguity_level,
                prediction.ambiguity_notes,
                prediction.confidence,
                payload.decision,
                json.dumps(payload.corrected_prerequisites),
                json.dumps(payload.corrected_enforcement_mechanisms),
                json.dumps(payload.corrected_triggers),
                payload.corrected_ambiguity_level,
                payload.corrected_ambiguity_notes,
                payload.notes,
            ],
        )
        return self._get_classification_label(target_key)

    def stats(self) -> Stats:
        return Stats(
            documents=self._count("source_documents"),
            extraction_items=len(self.extraction_items("all")),
            extraction_labels=self._count("extraction_labels"),
            classification_items=len(self.classification_items("all")),
            classification_labels=self._count("classification_labels"),
        )

    def _predicted_extraction_items(self) -> list[ExtractionItem]:
        rows = self.con.execute(
            """
            SELECT
                r.rule_id,
                r.document_id,
                r.source_path,
                r.rule_text,
                r.start_line,
                r.end_line,
                d.document_text
            FROM extracted_rules r
            JOIN source_documents d USING (document_id)
            ORDER BY r.source_path, r.start_line, r.rule_index
            """
        ).fetchall()
        labels = self._extraction_labels()
        items = []
        for row in rows:
            target_key = extraction_target_key(
                document_id=row[1],
                start_line=row[4],
                end_line=row[5],
                rule_text=row[3],
            )
            items.append(
                ExtractionItem(
                    target_key=target_key,
                    rule_id=row[0],
                    document_id=row[1],
                    source_path=row[2],
                    rule_text=row[3],
                    start_line=row[4],
                    end_line=row[5],
                    source_lines=self._source_lines(row[6], row[4], row[5]),
                    label=labels.get(target_key),
                )
            )
        return items

    def _missing_extraction_items(self) -> list[ExtractionItem]:
        rows = self.con.execute(
            """
            SELECT
                l.target_key,
                l.document_id,
                l.source_path,
                l.corrected_rule_text,
                l.corrected_start_line,
                l.corrected_end_line,
                d.document_text
            FROM extraction_labels l
            JOIN source_documents d USING (document_id)
            WHERE l.is_missing
            """
        ).fetchall()
        labels = self._extraction_labels()
        return [
            ExtractionItem(
                target_key=row[0],
                document_id=row[1],
                source_path=row[2],
                rule_id=None,
                rule_text=row[3],
                start_line=row[4],
                end_line=row[5],
                source_lines=self._source_lines(row[6], row[4], row[5]),
                label=labels.get(row[0]),
            )
            for row in rows
        ]

    def _source_lines(
        self,
        document_text: str,
        start_line: int,
        end_line: int,
        context: int = 4,
    ) -> list[SourceLine]:
        lines = document_text.replace("\r", "").split("\n")
        lower = max(1, start_line - context)
        upper = min(len(lines), end_line + context)
        return [
            SourceLine(line_number=i, text=lines[i - 1])
            for i in range(lower, upper + 1)
        ]

    def _extraction_labels(self) -> dict[str, ExtractionLabel]:
        rows = self.con.execute(
            """
            SELECT
                target_key,
                decision,
                corrected_rule_text,
                corrected_start_line,
                corrected_end_line,
                notes,
                is_missing
            FROM extraction_labels
            """
        ).fetchall()
        return {
            row[0]: ExtractionLabel(
                target_key=row[0],
                decision=row[1],
                corrected_rule_text=row[2],
                corrected_start_line=row[3],
                corrected_end_line=row[4],
                notes=row[5],
                is_missing=row[6],
            )
            for row in rows
        }

    def _classification_labels(self) -> dict[str, ClassificationLabel]:
        rows = self.con.execute(
            """
            SELECT
                target_key,
                decision,
                corrected_prerequisites,
                corrected_enforcement_mechanisms,
                corrected_triggers,
                corrected_ambiguity_level,
                corrected_ambiguity_notes,
                notes
            FROM classification_labels
            """
        ).fetchall()
        return {
            row[0]: ClassificationLabel(
                target_key=row[0],
                decision=row[1],
                corrected_prerequisites=self._json_array(row[2]),
                corrected_enforcement_mechanisms=self._json_array(row[3]),
                corrected_triggers=self._json_array(row[4]),
                corrected_ambiguity_level=row[5],
                corrected_ambiguity_notes=row[6],
                notes=row[7],
            )
            for row in rows
        }

    def _classification_predictions(self) -> dict[str, ClassificationPrediction]:
        rows = self.con.execute(
            """
            SELECT
                rule_id,
                prerequisites,
                enforcement_mechanisms,
                triggers,
                ambiguity_level,
                ambiguity_notes,
                confidence
            FROM classified_rules
            """
        ).fetchall()
        return {
            row[0]: ClassificationPrediction(
                prerequisites=self._json_array(row[1]),
                enforcement_mechanisms=self._json_array(row[2]),
                triggers=self._json_array(row[3]),
                ambiguity_level=row[4],
                ambiguity_notes=row[5],
                confidence=row[6],
            )
            for row in rows
        }

    def _get_extraction_label(self, target_key: str) -> ExtractionLabel:
        label = self._extraction_labels().get(target_key)
        if label is None:
            raise KeyError(target_key)
        return label

    def _get_classification_label(self, target_key: str) -> ClassificationLabel:
        label = self._classification_labels().get(target_key)
        if label is None:
            raise KeyError(target_key)
        return label

    def _find_extraction_item(self, target_key: str) -> ExtractionItem:
        for item in self.extraction_items("all"):
            if item.target_key == target_key:
                return item
        raise KeyError(target_key)

    def _find_classification_item(self, target_key: str) -> ClassificationItem:
        for item in self.classification_items("all"):
            if item.target_key == target_key:
                return item
        raise KeyError(target_key)

    def _count(self, table: str) -> int:
        return self.con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    def _json_array(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            parsed = json.loads(value)
        else:
            parsed = value
        return [str(item) for item in parsed]

    def _filter_by_status(self, items: list[Any], status: Status) -> list[Any]:
        if status == "all":
            return items
        if status == "labeled":
            return [item for item in items if item.label is not None]
        if status == "unlabeled":
            return [item for item in items if item.label is None]
        raise ValueError(f"Unknown status: {status}")
