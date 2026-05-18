from __future__ import annotations

import json

from fastapi.testclient import TestClient
from rules_models import PIPELINE_SCHEMA_SQL

from rules_labeling_backend.api import create_app
from rules_labeling_backend.db import LabelStore
from rules_labeling_backend.models import (
    ClassificationLabelIn,
    ExtractionLabelIn,
    MissingExtractionLabelIn,
)


def seed_pipeline_tables(store: LabelStore, rule_id: str = "rule-a") -> None:
    store.con.execute(
        PIPELINE_SCHEMA_SQL
    )
    store.con.execute(
        """
        INSERT INTO source_documents (
            document_id, source_path, document_name, document_text, content_sha256
        )
        VALUES ('doc-1', '/tmp/AGENTS.md', 'AGENTS.md', 'line one\nThe agent must inspect files.', 'sha')
        """
    )
    store.con.execute(
        """
        INSERT INTO extracted_rules (
            rule_id, document_id, source_path, rule_index, rule_text, start_line, end_line
        )
        VALUES (?, 'doc-1', '/tmp/AGENTS.md', 0, 'The agent must inspect files.', 2, 2)
        """,
        [rule_id],
    )
    store.con.execute(
        """
        INSERT INTO classified_rules (
            rule_id,
            document_id,
            source_path,
            rule_text,
            prerequisites,
            enforcement_mechanisms,
            triggers,
            ambiguity_level,
            ambiguity_notes,
            confidence
        )
        VALUES (
            ?, 'doc-1', '/tmp/AGENTS.md', 'The agent must inspect files.',
            ?::JSON, ?::JSON, ?::JSON, 'low', 'clear', 0.9
        )
        """,
        [rule_id, json.dumps([]), json.dumps(["review"]), json.dumps(["before editing"])],
    )


def test_label_tables_are_created_idempotently() -> None:
    store = LabelStore(":memory:")

    store.ensure_label_schema()
    store.ensure_label_schema()

    tables = {
        row[0]
        for row in store.con.execute(
            "SELECT table_name FROM duckdb_tables() WHERE table_name LIKE '%labels'"
        ).fetchall()
    }
    assert {"extraction_labels", "classification_labels"} <= tables


def test_extraction_label_survives_rule_id_change() -> None:
    store = LabelStore(":memory:")
    seed_pipeline_tables(store, "rule-before")
    item = store.extraction_items()[0]

    store.upsert_extraction_label(
        item.target_key,
        ExtractionLabelIn(decision="accept", notes="looks good"),
    )
    store.con.execute("UPDATE extracted_rules SET rule_id = 'rule-after'")

    rerun_item = store.extraction_items()[0]
    assert rerun_item.rule_id == "rule-after"
    assert rerun_item.target_key == item.target_key
    assert rerun_item.label is not None
    assert rerun_item.label.notes == "looks good"


def test_classification_label_survives_classification_rerun() -> None:
    store = LabelStore(":memory:")
    seed_pipeline_tables(store)
    item = store.classification_items()[0]

    store.upsert_classification_label(
        item.target_key,
        ClassificationLabelIn(
            decision="correct",
            corrected_prerequisites=["before editing"],
            corrected_enforcement_mechanisms=["review"],
            corrected_triggers=["code change"],
            corrected_ambiguity_level="low",
            corrected_ambiguity_notes="clear",
            notes="updated",
        ),
    )
    store.con.execute("UPDATE classified_rules SET confidence = 0.1, ambiguity_notes = 'rerun'")

    rerun_item = store.classification_items()[0]
    assert rerun_item.target_key == item.target_key
    assert rerun_item.prediction is not None
    assert rerun_item.prediction.confidence == 0.1
    assert rerun_item.label is not None
    assert rerun_item.label.corrected_triggers == ["code change"]


def test_missing_rule_labels_are_queryable_with_candidates() -> None:
    store = LabelStore(":memory:")
    seed_pipeline_tables(store)

    store.add_missing_extraction_label(
        MissingExtractionLabelIn(
            document_id="doc-1",
            source_path="/tmp/AGENTS.md",
            rule_text="The agent cannot commit secrets.",
            start_line=2,
            end_line=2,
            notes="missed",
        )
    )

    items = store.extraction_items()
    assert len(items) == 2
    assert any(item.label and item.label.is_missing for item in items)


def test_api_smoke() -> None:
    client = TestClient(create_app(":memory:"))
    assert client.get("/api/health").json() == {"status": "ok"}


def test_api_returns_extraction_items(tmp_path) -> None:
    db_path = tmp_path / "labels.duckdb"
    store = LabelStore(db_path)
    seed_pipeline_tables(store)
    store.con.close()

    client = TestClient(create_app(db_path))

    response = client.get("/api/extraction-items?status=unlabeled")
    assert response.status_code == 200
    assert response.json()[0]["rule_text"] == "The agent must inspect files."
