from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Iterable

import duckdb
from rules_models import PIPELINE_SCHEMA_SQL


REQUIRED_DUCKDB_VERSION = "1.5.2"
REQUIRED_FLOCK_EXTENSION_VERSION = "ed1ee54"


@dataclass(frozen=True)
class PipelineConfig:
    inputs: list[Path]
    db_path: Path
    run_extract: bool
    run_classify: bool
    force: bool
    model_alias: str
    model_name: str
    provider: str
    api_key_env: str
    base_url_env: str
    temperature: float
    batch_size: int
    no_install: bool
    extract_prompt_name: str
    extract_prompt_text: str
    classify_prompt_name: str
    classify_prompt_text: str


def discover_files(inputs: Iterable[Path]) -> list[Path]:
    paths: list[Path] = []
    for input_path in inputs:
        path = input_path.expanduser().resolve()
        if path.is_file():
            paths.append(path)
        elif path.is_dir():
            paths.extend(
                p
                for p in path.rglob("*")
                if p.is_file() and not any(part.startswith(".") for part in p.parts)
            )
        else:
            raise FileNotFoundError(f"Input path does not exist: {input_path}")
    return sorted(set(paths))


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def connect(db_path: Path) -> duckdb.DuckDBPyConnection:
    validate_duckdb_version()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute("LOAD json;")
    return con


def install_and_load_extensions(con: duckdb.DuckDBPyConnection, no_install: bool) -> None:
    validate_duckdb_version()
    if not no_install:
        con.execute("INSTALL flock FROM community;")
        con.execute("INSTALL json;")
    con.execute("LOAD flock;")
    con.execute("LOAD json;")
    validate_flock_version(con)


def validate_duckdb_version() -> None:
    if duckdb.__version__ != REQUIRED_DUCKDB_VERSION:
        raise RuntimeError(
            f"DuckDB {REQUIRED_DUCKDB_VERSION} is required; found {duckdb.__version__}."
        )


def validate_flock_version(con: duckdb.DuckDBPyConnection) -> None:
    row = con.execute(
        """
        SELECT extension_version
        FROM duckdb_extensions()
        WHERE extension_name = 'flock' AND loaded
        """
    ).fetchone()
    loaded_version = row[0] if row else None
    if loaded_version != REQUIRED_FLOCK_EXTENSION_VERSION:
        raise RuntimeError(
            "Flock extension "
            f"{REQUIRED_FLOCK_EXTENSION_VERSION} is required; found {loaded_version}."
        )


def configure_flock_model(
    con: duckdb.DuckDBPyConnection,
    *,
    model_alias: str,
    model_name: str,
    provider: str,
    api_key_env: str,
    base_url_env: str,
    temperature: float,
    batch_size: int,
) -> None:
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(f"{api_key_env} is required to run Flock-backed LLM stages.")

    base_url = os.environ.get(base_url_env)
    if base_url:
        con.execute(
            "CREATE OR REPLACE SECRET (TYPE OPENAI, BASE_URL ?, API_KEY ?);",
            [base_url, api_key],
        )
    elif provider.lower() == "openai":
        con.execute(
            "CREATE OR REPLACE SECRET (TYPE OPENAI, API_KEY ?);",
            [api_key],
        )

    model_options = {
        "tuple_format": "JSON",
        "batch_size": batch_size,
        "model_parameters": {"temperature": temperature},
    }
    quoted_alias = sql_string(model_alias)
    try:
        con.execute(f"DELETE MODEL {quoted_alias};")
    except duckdb.Error:
        pass

    con.execute(
        "CREATE MODEL("
        f"{quoted_alias}, "
        f"{sql_string(model_name)}, "
        f"{sql_string(provider)}, "
        f"{json.dumps(model_options)}"
        ");"
    )


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def install_prompt(
    con: duckdb.DuckDBPyConnection,
    *,
    prompt_name: str,
    prompt_text: str,
) -> None:
    if not prompt_name:
        raise ValueError("prompt_name must not be empty.")
    if not prompt_text:
        raise ValueError("prompt_text must not be empty.")

    quoted_name = sql_string(prompt_name)
    con.execute(f"DELETE PROMPT {quoted_name};")
    con.execute(f"CREATE PROMPT({quoted_name}, {sql_string(prompt_text)});")


def ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(PIPELINE_SCHEMA_SQL)


def ingest_documents(con: duckdb.DuckDBPyConnection, inputs: list[Path]) -> int:
    files = discover_files(inputs)
    rows = []
    for path in files:
        text = read_text(path)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        rows.append((digest, str(path), path.name, text, digest))

    if rows:
        con.executemany(
            """
            INSERT INTO source_documents (
                document_id, source_path, document_name, document_text, content_sha256
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (document_id) DO UPDATE SET
                source_path = excluded.source_path,
                document_name = excluded.document_name,
                document_text = excluded.document_text,
                content_sha256 = excluded.content_sha256,
                ingested_at = now()
            """,
            rows,
        )
    return len(rows)


def run_sql(
    con: duckdb.DuckDBPyConnection,
    sql_text: str,
    *,
    model_alias: str,
    force: bool,
    prompt_variable: str | None = None,
    prompt_name: str | None = None,
) -> None:
    con.execute("SET VARIABLE rules_model_alias = ?;", [model_alias])
    con.execute("SET VARIABLE force_rerun = ?;", [force])
    if prompt_variable is not None:
        if prompt_name is None:
            raise ValueError("prompt_name is required when prompt_variable is set.")
        con.execute(f"SET VARIABLE {prompt_variable} = ?;", [prompt_name])
    con.execute(sql_text)


def read_resource_text(relative_path: str) -> str:
    if relative_path == "schema.sql":
        return PIPELINE_SCHEMA_SQL
    parts = relative_path.split("/")
    resource = resources.files("rules_in_the_wild").joinpath(*parts)
    return resource.read_text(encoding="utf-8")


def summarize(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    row = con.execute(
        """
        SELECT
            (SELECT count(*) FROM source_documents) AS documents,
            (SELECT count(*) FROM extracted_rules) AS extracted_rules,
            (SELECT count(*) FROM classified_rules) AS classified_rules
        """
    ).fetchone()
    return {
        "documents": row[0],
        "extracted_rules": row[1],
        "classified_rules": row[2],
    }


def run_pipeline(config: PipelineConfig) -> dict[str, int]:
    if config.run_extract and not config.inputs:
        raise ValueError("inputs are required when running extraction.")

    con = connect(config.db_path.expanduser().resolve())
    ensure_schema(con)
    install_and_load_extensions(con, config.no_install)
    configure_flock_model(
        con,
        model_alias=config.model_alias,
        model_name=config.model_name,
        provider=config.provider,
        api_key_env=config.api_key_env,
        base_url_env=config.base_url_env,
        temperature=config.temperature,
        batch_size=config.batch_size,
    )
    install_prompt(
        con,
        prompt_name=config.extract_prompt_name,
        prompt_text=config.extract_prompt_text,
    )
    install_prompt(
        con,
        prompt_name=config.classify_prompt_name,
        prompt_text=config.classify_prompt_text,
    )

    if config.run_extract:
        ingest_documents(con, config.inputs)
        run_sql(
            con,
            read_resource_text("extract/extract_rules.sql"),
            model_alias=config.model_alias,
            force=config.force,
            prompt_variable="rules_extract_prompt_name",
            prompt_name=config.extract_prompt_name,
        )

    if config.run_classify:
        run_sql(
            con,
            read_resource_text("classify/classify_rules.sql"),
            model_alias=config.model_alias,
            force=config.force,
            prompt_variable="rules_classify_prompt_name",
            prompt_name=config.classify_prompt_name,
        )

    return summarize(con)
