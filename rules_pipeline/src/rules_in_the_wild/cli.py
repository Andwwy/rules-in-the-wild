from __future__ import annotations

import argparse
import os
from importlib import resources
from pathlib import Path

from rules_in_the_wild.main import PipelineConfig, run_pipeline


DEFAULT_DB = Path.cwd() / "rules.duckdb"
DEFAULT_MODEL_ALIAS = "rules_model"
DEFAULT_MODEL_NAME = "gpt-5.4-mini"
DEFAULT_PROVIDER = "openai"
DEFAULT_API_KEY_ENV = "OPENAI_API_KEY"
DEFAULT_BASE_URL_ENV = "OPENAI_BASE_URL"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_BATCH_SIZE = 8
DEFAULT_EXTRACT_PROMPT_FILE = Path.cwd() / "prompts" / "extract.md"
DEFAULT_CLASSIFY_PROMPT_FILE = Path.cwd() / "prompts" / "classify.md"
DEFAULT_EXTRACT_PROMPT_NAME = "rules_extract_v1"
DEFAULT_CLASSIFY_PROMPT_NAME = "rules_classify_v1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the DuckDB/Flock rules extraction and classification pipeline."
    )
    parser.add_argument(
        "--input",
        "-i",
        action="append",
        type=Path,
        default=[],
        help="Input file or directory. May be repeated. Required when running extraction.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"DuckDB database path. Defaults to {DEFAULT_DB.name}.",
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Run the extraction stage.",
    )
    parser.add_argument(
        "--classify",
        action="store_true",
        help="Run the classification stage.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run LLM stages for documents/rules that already have outputs.",
    )
    parser.add_argument(
        "--model-alias",
        default=DEFAULT_MODEL_ALIAS,
        help="Name used for the Flock MODEL object.",
    )
    parser.add_argument(
        "--model-name",
        default=os.environ.get("RULES_MODEL_NAME", DEFAULT_MODEL_NAME),
        help="Provider model name. Can also be set with RULES_MODEL_NAME.",
    )
    parser.add_argument(
        "--provider",
        default=os.environ.get("RULES_PROVIDER", DEFAULT_PROVIDER),
        help="Flock provider name. Defaults to openai.",
    )
    parser.add_argument(
        "--api-key-env",
        default=DEFAULT_API_KEY_ENV,
        help="Environment variable containing the provider API key.",
    )
    parser.add_argument(
        "--base-url-env",
        default=DEFAULT_BASE_URL_ENV,
        help="Optional environment variable for an OpenAI-compatible base URL.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help="LLM temperature passed to Flock model parameters.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Flock batch size for LLM calls.",
    )
    parser.add_argument(
        "--no-install",
        action="store_true",
        help="Skip INSTALL statements for DuckDB extensions.",
    )
    parser.add_argument(
        "--extract-prompt-file",
        type=Path,
        default=DEFAULT_EXTRACT_PROMPT_FILE,
        help="Markdown/text file containing an extraction prompt.",
    )
    parser.add_argument(
        "--classify-prompt-file",
        type=Path,
        default=DEFAULT_CLASSIFY_PROMPT_FILE,
        help="Markdown/text file containing a classification prompt.",
    )
    parser.add_argument(
        "--extract-prompt",
        help="Literal extraction prompt text. Overrides --extract-prompt-file.",
    )
    parser.add_argument(
        "--classify-prompt",
        help="Literal classification prompt text. Overrides --classify-prompt-file.",
    )
    parser.add_argument(
        "--extract-prompt-name",
        default=DEFAULT_EXTRACT_PROMPT_NAME,
        help="Flock prompt object name for the extraction prompt.",
    )
    parser.add_argument(
        "--classify-prompt-name",
        default=DEFAULT_CLASSIFY_PROMPT_NAME,
        help="Flock prompt object name for the classification prompt.",
    )
    return parser.parse_args(argv)


def load_prompt_file(path: Path, package_resource: str) -> str:
    try:
        return path.expanduser().read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        default_paths = {DEFAULT_EXTRACT_PROMPT_FILE, DEFAULT_CLASSIFY_PROMPT_FILE}
        if path in default_paths:
            return (
                resources.files("rules_in_the_wild")
                .joinpath("prompts", package_resource)
                .read_text(encoding="utf-8")
            )
        raise SystemExit(f"Prompt file does not exist: {path}") from exc


def resolve_prompt(
    *,
    prompt_file: Path,
    prompt_text: str | None,
    package_resource: str,
) -> str:
    if prompt_text is not None:
        return prompt_text
    return load_prompt_file(prompt_file, package_resource)


def config_from_args(args: argparse.Namespace) -> PipelineConfig:
    run_extract = args.extract or not args.classify
    run_classify = args.classify or not args.extract

    if run_extract and not args.input:
        raise SystemExit("--input is required when running extraction.")

    return PipelineConfig(
        inputs=args.input,
        db_path=args.db,
        run_extract=run_extract,
        run_classify=run_classify,
        force=args.force,
        model_alias=args.model_alias,
        model_name=args.model_name,
        provider=args.provider,
        api_key_env=args.api_key_env,
        base_url_env=args.base_url_env,
        temperature=args.temperature,
        batch_size=args.batch_size,
        no_install=args.no_install,
        extract_prompt_name=args.extract_prompt_name,
        extract_prompt_text=resolve_prompt(
            prompt_file=args.extract_prompt_file,
            prompt_text=args.extract_prompt,
            package_resource="extract.md",
        ),
        classify_prompt_name=args.classify_prompt_name,
        classify_prompt_text=resolve_prompt(
            prompt_file=args.classify_prompt_file,
            prompt_text=args.classify_prompt,
            package_resource="classify.md",
        ),
    )


def main(argv: list[str] | None = None) -> None:
    config = config_from_args(parse_args(argv))
    stats = run_pipeline(config)
    print(
        "Done: "
        f"{stats['documents']} document(s), "
        f"{stats['extracted_rules']} extracted rule(s), "
        f"{stats['classified_rules']} classified rule(s)."
    )


if __name__ == "__main__":
    main()
