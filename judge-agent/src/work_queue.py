"""Work queue for the judge: pull unjudged rules, write decisions back.

The `rule` table is the queue. A rule is "unjudged" iff no row exists in
`rule_llm_decision` with `parse_ok = TRUE` for it. (Parse failures are
recorded but not "consumed" — the operator can rerun against them once the
prompt has been tightened.)

We append to `rule_llm_decision` (append-only history). The
`triggered_by` column is always `'initial'` here — `prompt_revised` and
`manual_rerun` flows go through the admin UI, not this agent.
"""

import json

import duckdb

from src.judge import JUDGE_MODEL, JudgeResult


def next_batch(con: duckdb.DuckDBPyConnection, limit: int = 20) -> list[tuple[str, str, str]]:
    """Returns up to `limit` rows: (rule_id, rule_text, source_kind)."""
    rows = con.execute(
        """
        SELECT r.id::VARCHAR    AS rule_id,
               r.rule_text,
               f.kind::VARCHAR  AS source_kind
        FROM rule r
        JOIN rules_file f ON f.id = r.rules_file_id
        WHERE NOT EXISTS (
            SELECT 1 FROM rule_llm_decision d
            WHERE d.rule_id = r.id AND d.parse_ok = TRUE
        )
        ORDER BY r.extracted_at ASC
        LIMIT ?
        """,
        [limit],
    ).fetchall()
    return [(row[0], row[1], row[2]) for row in rows]


def record_decision(
    con: duckdb.DuckDBPyConnection,
    rule_id: str,
    result: JudgeResult,
    prompt_version: str,
) -> None:
    label = result.label
    values = label.values if label else {}
    # JSON column on TIMESTAMPTZ defaults in DuckDB schema; positional binding.
    # Every enum column needs an explicit cast — DuckDB's positional parameter
    # binding won't auto-coerce strings to enum types, even when the string is
    # a valid member. Without these casts the INSERT fails with
    # "Could not convert string 'X' to UINT8" (UINT8 is the enum storage type).
    con.execute(
        """
        INSERT INTO rule_llm_decision (
            rule_id, judge_model, judge_prompt_version, triggered_by,
            prompt_messages, raw_response, parse_ok, parse_error,
            specificity, cognitive_load, constraint_level,
            enforcement_mechanism, enforcement_scope, enforcement_trigger,
            rule_kind, artifacts_required, confidence, rationale,
            latency_ms, input_tokens, output_tokens
        ) VALUES (
            ?, ?, ?, 'initial',
            ?::JSON, ?, ?, ?,
            ?::rule_specificity, ?::rule_cognitive_load, ?::rule_constraint_level,
            ?::enforcement_mechanism, ?::enforcement_scope, ?::enforcement_trigger,
            ?::rule_kind, ?::artifact_required[], ?, ?,
            ?, ?, ?
        )
        """,
        [
            rule_id,
            JUDGE_MODEL,
            prompt_version,
            json.dumps(result.prompt_messages),
            result.raw_response,
            result.parse_ok,
            result.parse_error,
            values.get("rule_specificity"),
            values.get("rule_cognitive_load"),
            values.get("rule_constraint_level"),
            values.get("enforcement_mechanism"),
            values.get("enforcement_scope"),
            values.get("enforcement_trigger"),
            values.get("rule_kind"),
            (label.artifacts_required if label else []),
            (label.confidence if label else None),
            (label.rationale if label else None),
            result.latency_ms,
            result.input_tokens,
            result.output_tokens,
        ],
    )
