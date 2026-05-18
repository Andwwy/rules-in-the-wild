from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
from rules_models import PIPELINE_SCHEMA_SQL


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: seed_e2e_db.py /path/to/e2e.duckdb")

    db_path = Path(sys.argv[1])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    con = duckdb.connect(str(db_path))
    con.execute("LOAD json;")
    con.execute(PIPELINE_SCHEMA_SQL)
    con.execute(
        """
        INSERT INTO source_documents (
            document_id, source_path, document_name, document_text, content_sha256
        )
        VALUES (
            'doc-e2e',
            '/tmp/AGENTS.md',
            'AGENTS.md',
            'Intro\nThe agent must inspect files before editing.\nOutro',
            'sha-e2e'
        )
        """
    )
    con.execute(
        """
        INSERT INTO extracted_rules (
            rule_id, document_id, source_path, rule_index, rule_text, start_line, end_line
        )
        VALUES (
            'rule-e2e',
            'doc-e2e',
            '/tmp/AGENTS.md',
            0,
            'The agent must inspect files before editing.',
            2,
            2
        )
        """
    )
    con.execute(
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
            'rule-e2e',
            'doc-e2e',
            '/tmp/AGENTS.md',
            'The agent must inspect files before editing.',
            ?::JSON,
            ?::JSON,
            ?::JSON,
            'low',
            'The timing is explicit.',
            0.9
        )
        """,
        [
            json.dumps(["before editing"]),
            json.dumps(["review"]),
            json.dumps(["file edit"]),
        ],
    )
    con.close()


if __name__ == "__main__":
    main()
