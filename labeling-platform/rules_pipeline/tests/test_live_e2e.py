import os
from pathlib import Path

import duckdb
import pytest

from rules_in_the_wild import cli
from rules_in_the_wild import main as pipeline


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY is required for the live Flock/OpenAI E2E test.",
)
def test_live_sample_extract_and_classify() -> None:
    project_root = Path(__file__).resolve().parents[1]

    con = duckdb.connect(":memory:")
    pipeline.ensure_schema(con)
    pipeline.install_and_load_extensions(con, no_install=False)
    pipeline.configure_flock_model(
        con,
        model_alias="rules_model",
        model_name=os.environ.get("RULES_LIVE_MODEL", "gpt-5.4-mini"),
        provider="openai",
        api_key_env="OPENAI_API_KEY",
        base_url_env="OPENAI_BASE_URL",
        temperature=0.0,
        batch_size=1,
    )
    pipeline.install_prompt(
        con,
        prompt_name="rules_extract_v1",
        prompt_text=cli.load_prompt_file(cli.DEFAULT_EXTRACT_PROMPT_FILE, "extract.md"),
    )
    pipeline.install_prompt(
        con,
        prompt_name="rules_classify_v1",
        prompt_text=cli.load_prompt_file(
            cli.DEFAULT_CLASSIFY_PROMPT_FILE, "classify.md"
        ),
    )
    pipeline.ingest_documents(con, [project_root / "samples"])
    pipeline.run_sql(
        con,
        pipeline.read_resource_text("extract/extract_rules.sql"),
        model_alias="rules_model",
        force=True,
        prompt_variable="rules_extract_prompt_name",
        prompt_name="rules_extract_v1",
    )
    pipeline.run_sql(
        con,
        pipeline.read_resource_text("classify/classify_rules.sql"),
        model_alias="rules_model",
        force=True,
        prompt_variable="rules_classify_prompt_name",
        prompt_name="rules_classify_v1",
    )

    documents, extracted_rules, classified_rules = con.execute(
        """
        SELECT
            (SELECT count(*) FROM source_documents),
            (SELECT count(*) FROM extracted_rules),
            (SELECT count(*) FROM classified_rules)
        """
    ).fetchone()

    assert documents == 1
    assert extracted_rules > 0
    assert classified_rules == extracted_rules
