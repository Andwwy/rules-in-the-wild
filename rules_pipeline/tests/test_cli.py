from pathlib import Path

import duckdb
import pytest

from rules_in_the_wild import cli
from rules_in_the_wild import main as pipeline


def test_parse_args_defaults_to_both_stages() -> None:
    args = cli.parse_args(["--input", "samples"])

    assert args.input == [Path("samples")]
    assert args.extract is False
    assert args.classify is False
    assert args.model_name == "gpt-5.4-mini"


def test_config_from_args_supplies_all_pipeline_fields() -> None:
    config = cli.config_from_args(cli.parse_args(["--input", "samples"]))

    assert config.inputs == [Path("samples")]
    assert config.db_path == cli.DEFAULT_DB
    assert config.run_extract is True
    assert config.run_classify is True
    assert config.force is False
    assert config.model_alias == cli.DEFAULT_MODEL_ALIAS
    assert config.model_name == cli.DEFAULT_MODEL_NAME
    assert config.provider == cli.DEFAULT_PROVIDER
    assert config.api_key_env == cli.DEFAULT_API_KEY_ENV
    assert config.base_url_env == cli.DEFAULT_BASE_URL_ENV
    assert config.temperature == cli.DEFAULT_TEMPERATURE
    assert config.batch_size == cli.DEFAULT_BATCH_SIZE
    assert config.no_install is False
    assert config.extract_prompt_name == cli.DEFAULT_EXTRACT_PROMPT_NAME
    assert config.extract_prompt_text == cli.DEFAULT_EXTRACT_PROMPT_FILE.read_text(
        encoding="utf-8"
    )
    assert config.classify_prompt_name == cli.DEFAULT_CLASSIFY_PROMPT_NAME
    assert config.classify_prompt_text == cli.DEFAULT_CLASSIFY_PROMPT_FILE.read_text(
        encoding="utf-8"
    )


def test_prompt_overrides_prefer_literal_then_file(tmp_path: Path) -> None:
    prompt_file = tmp_path / "extract.txt"
    prompt_file.write_text("file extract", encoding="utf-8")

    config = cli.config_from_args(
        cli.parse_args(
            [
                "--input",
                "samples",
                "--extract-prompt-file",
                str(prompt_file),
                "--classify-prompt",
                "literal classify",
            ]
        )
    )

    assert config.extract_prompt_text == "file extract"
    assert config.classify_prompt_text == "literal classify"


def test_main_requires_input_when_extraction_would_run() -> None:
    with pytest.raises(SystemExit, match="--input is required"):
        cli.main(["--db", ":memory:"])


def test_sql_string_escapes_single_quotes() -> None:
    assert pipeline.sql_string("model's alias") == "'model''s alias'"


def test_runtime_versions_are_pinned() -> None:
    assert pipeline.REQUIRED_DUCKDB_VERSION == "1.5.2"
    assert pipeline.REQUIRED_FLOCK_EXTENSION_VERSION == "ed1ee54"


def test_discover_files_recurses_and_skips_hidden_paths(tmp_path: Path) -> None:
    visible = tmp_path / "docs" / "AGENTS.md"
    hidden = tmp_path / "docs" / ".hidden" / "secret.md"
    visible.parent.mkdir()
    hidden.parent.mkdir()
    visible.write_text("visible", encoding="utf-8")
    hidden.write_text("hidden", encoding="utf-8")

    assert pipeline.discover_files([tmp_path / "docs"]) == [visible.resolve()]


def test_ingest_documents_is_idempotent(tmp_path: Path) -> None:
    document = tmp_path / "AGENTS.md"
    document.write_text("The agent must inspect files.", encoding="utf-8")
    con = duckdb.connect(":memory:")
    pipeline.ensure_schema(con)

    assert pipeline.ingest_documents(con, [document]) == 1
    assert pipeline.ingest_documents(con, [document]) == 1
    assert con.execute("SELECT count(*) FROM source_documents").fetchone()[0] == 1


def test_package_sql_resources_are_available() -> None:
    assert "CREATE TABLE" in pipeline.read_resource_text("schema.sql")
    assert "rule_text" in pipeline.read_resource_text("extract/extract_rules.sql")
    assert "ambiguity_level" in pipeline.read_resource_text("classify/classify_rules.sql")
