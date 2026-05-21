"""Perplexity Agent API as the taxonomy judge (prototype-only routing).

At boot: reads pg_enum to learn the current taxonomy values (schema-driven prompt).
Per rule: returns one value per axis plus a confidence and a one-sentence rationale.

Routing note:
    We used to call Anthropic directly via the `anthropic` SDK. Switched to
    Perplexity's Agent API so the prototype only needs ONE paid key
    (PERPLEXITY_API_KEY) — Perplexity passes through `anthropic/claude-haiku-4-5`
    at no markup. Same model, same prompt, different transport.
    Pre-prod we'll revert to the Anthropic SDK (a ~20-line diff).
"""

import json
import os
import re
from dataclasses import dataclass

import httpx
import psycopg
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import JUDGE_MODEL, JUDGE_PROMPT_VERSION
from .db import enum_values


TAXONOMY_AXES = [
    "rule_specificity",
    "rule_cognitive_load",
    "rule_constraint_level",
    "enforcement_mechanism",
    "enforcement_scope",
    "enforcement_trigger",
    "rule_kind",
]


@dataclass
class JudgeLabel:
    values: dict[str, str]              # axis -> chosen value
    artifacts_required: list[str]
    confidence: float
    rationale: str


def _build_prompt(conn: psycopg.Connection) -> str:
    lines = [
        "You classify a single rule written for an LLM coding agent.",
        "Return ONLY a JSON object — no prose, no markdown fences.",
        "",
        "For each axis below, pick exactly one value from the allowed list.",
        "",
    ]
    for axis in TAXONOMY_AXES:
        vals = enum_values(conn, axis)
        lines.append(f"  {axis}: one of [{', '.join(vals)}]")
    artifact_vals = enum_values(conn, "artifact_required")
    lines.append(f"  artifacts_required: list (possibly empty) of [{', '.join(artifact_vals)}]")
    lines.append("  confidence: float in [0, 1]")
    lines.append("  rationale: one sentence, ≤ 200 chars")
    lines.append("")
    lines.append("Output schema example:")
    lines.append(json.dumps({
        "rule_specificity": "project_specific",
        "rule_cognitive_load": "zero_lookup",
        "rule_constraint_level": "output_content",
        "enforcement_mechanism": "llm_judge",
        "enforcement_scope": "local",
        "enforcement_trigger": "final_output",
        "rule_kind": "repository_conventions",
        "artifacts_required": ["output"],
        "confidence": 0.72,
        "rationale": "Format constraint on the model's final text; can only be checked by an LLM judge.",
    }, indent=2))
    return "\n".join(lines)


PERPLEXITY_BASE = "https://api.perplexity.ai"


def _extract_text(body: dict) -> str:
    """Perplexity Agent API mirrors OpenAI's Responses shape:
       body.output[*].content[*] = {"type": "output_text", "text": "..."}
    Concatenate every output_text segment (usually one)."""
    parts: list[str] = []
    for item in body.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                parts.append(content.get("text", ""))
    return "".join(parts)


_FENCE_OPEN_RE = re.compile(r"^\s*```(?:json)?\s*", re.IGNORECASE)
_FENCE_CLOSE_RE = re.compile(r"\s*```\s*$")
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json(text: str) -> dict:
    """Tolerant JSON extraction. Tries direct parse, then strips ``` fences,
    then falls back to a greedy {…} match. Haiku tends to wrap JSON in
    ```json fences even when asked not to; allow for prose preambles too."""
    text = text.strip()
    for candidate in (
        text,
        _FENCE_CLOSE_RE.sub("", _FENCE_OPEN_RE.sub("", text)),
    ):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    m = _JSON_OBJECT_RE.search(text)
    if m:
        return json.loads(m.group(0))  # last-chance; raises if still invalid
    raise json.JSONDecodeError("no JSON object found", text, 0)


class Judge:
    def __init__(self, conn: psycopg.Connection):
        self.system_prompt = _build_prompt(conn)
        self._client = httpx.Client(
            base_url=PERPLEXITY_BASE,
            headers={
                "Authorization": f"Bearer {os.environ['PERPLEXITY_API_KEY']}",
                "Content-Type": "application/json",
            },
            timeout=60,
        )

    # Retry only on transport errors. JSONDecodeError / KeyError on a bad
    # response are deterministic — re-asking the model wastes tokens.
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    def classify(self, rule_text: str, source_kind: str) -> JudgeLabel:
        user = f"source_kind: {source_kind}\nrule: {rule_text}"
        # Perplexity's Agent API takes a single `input` string; we inline the
        # system prompt with explicit SYSTEM/USER markers since the endpoint
        # doesn't take a separate system parameter.
        prompt = (
            f"SYSTEM:\n{self.system_prompt}\n\n"
            f"USER:\n{user}\n\n"
            "Respond with ONLY the JSON object."
        )
        resp = self._client.post(
            "/v1/agent",
            json={
                "model": JUDGE_MODEL,
                "input": prompt,
                "max_output_tokens": 512,
            },
        )
        resp.raise_for_status()
        body = resp.json()
        obj = _parse_json(_extract_text(body))
        return JudgeLabel(
            values={a: obj[a] for a in TAXONOMY_AXES},
            artifacts_required=obj.get("artifacts_required", []),
            confidence=float(obj.get("confidence", 0.5)),
            rationale=obj.get("rationale", "")[:500],
        )

    @property
    def model_id(self) -> str:
        return JUDGE_MODEL

    @property
    def prompt_version(self) -> str:
        return JUDGE_PROMPT_VERSION
