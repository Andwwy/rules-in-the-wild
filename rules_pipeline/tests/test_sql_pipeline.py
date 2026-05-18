from pathlib import Path

import duckdb

from rules_in_the_wild import main as pipeline


def test_extract_and_classify_sql_with_stubbed_llm(tmp_path: Path) -> None:
    document = tmp_path / "AGENTS.md"
    document.write_text("The agent must inspect relevant files.", encoding="utf-8")

    con = duckdb.connect(":memory:")
    con.execute("LOAD flock;")
    con.execute("LOAD json;")
    pipeline.ensure_schema(con)
    pipeline.ingest_documents(con, [document])

    extract_output = (
        "The agent must inspect relevant files.\t"
        "1\t"
        "1"
    )
    con.execute(
        f"CREATE MACRO llm_complete(a, b) AS ({pipeline.sql_string(extract_output)});"
    )
    pipeline.run_sql(
        con,
        pipeline.read_resource_text("extract/extract_rules.sql"),
        model_alias="rules_model",
        force=True,
        prompt_variable="rules_extract_prompt_name",
        prompt_name="rules_extract_v1",
    )

    extracted = con.execute(
        """
        SELECT
            rule_text,
            start_line,
            end_line,
            document_id,
            source_path
        FROM extracted_rules
        """
    ).fetchone()
    document_id = con.execute("SELECT document_id FROM source_documents").fetchone()[0]
    assert extracted == (
        "The agent must inspect relevant files.",
        1,
        1,
        document_id,
        str(document.resolve()),
    )

    con.execute("DROP MACRO llm_complete;")
    classify_output = (
        "before making changes\t"
        "human review\t"
        "code modification request\t"
        "low\t"
        "The actor and required action are explicit.\t"
        "0.87"
    )
    con.execute(
        f"CREATE MACRO llm_complete(a, b) AS ({pipeline.sql_string(classify_output)});"
    )
    pipeline.run_sql(
        con,
        pipeline.read_resource_text("classify/classify_rules.sql"),
        model_alias="rules_model",
        force=True,
        prompt_variable="rules_classify_prompt_name",
        prompt_name="rules_classify_v1",
    )

    classified = con.execute(
        """
        SELECT
            json_extract_string(prerequisites, '$[0]'),
            json_extract_string(enforcement_mechanisms, '$[0]'),
            json_extract_string(triggers, '$[0]'),
            ambiguity_level,
            confidence
        FROM classified_rules
        """
    ).fetchone()
    assert classified == (
        "before making changes",
        "human review",
        "code modification request",
        "low",
        0.87,
    )
