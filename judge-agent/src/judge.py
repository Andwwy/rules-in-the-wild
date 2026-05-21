"""Judge: Haiku-4.5-via-Perplexity classifier for individual rules.

Differs from prototype/src/judge.py in two ways:
  1. System prompt is read from a markdown file (`prompts/judge.md`) — easier
     iteration; container restart picks up edits because the prompts dir is
     mounted in.
  2. classify() returns a `JudgeResult` that carries everything
     `rule_llm_decision` needs (prompt messages, raw response, parse status,
     tokens, latency) so the caller can write the row in one INSERT.

prompt_version = first 12 hex chars of SHA-256(raw_prompt + enum_block).
Editing either bumps the version automatically — no manual config bump needed.
"""

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import duckdb
import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.db import enum_values


JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "anthropic/claude-haiku-4-5")
PROMPT_PATH = Path(os.environ.get("JUDGE_PROMPT_PATH", "/app/prompts/judge.md"))
PERPLEXITY_BASE = "https://api.perplexity.ai"

# These are the enum *type names* — the prompt asks the model to use these as
# JSON keys (because they're maximally descriptive). When writing to
# `rule_llm_decision`, the column names drop the `rule_` prefix for the first
# three axes; see work_queue.py for the mapping.
TAXONOMY_AXES = [
    "rule_specificity",
    "rule_cognitive_load",
    "rule_constraint_level",
    "enforcement_mechanism",
    "enforcement_scope",
    "enforcement_trigger",
    "rule_kind",
]

ENUM_BLOCK_PLACEHOLDER = "{{ENUM_VALUES_BLOCK}}"


@dataclass
class JudgeLabel:
    values: dict[str, str]
    artifacts_required: list[str]
    confidence: float
    rationale: str


@dataclass
class JudgeResult:
    label: Optional[JudgeLabel]
    prompt_messages: list[dict]
    raw_response: str
    parse_ok: bool
    parse_error: Optional[str]
    latency_ms: int
    input_tokens: int
    output_tokens: int


def _build_enum_block(con: duckdb.DuckDBPyConnection) -> str:
    lines = ["Allowed values per axis:"]
    for axis in TAXONOMY_AXES:
        vals = enum_values(con, axis)
        lines.append(f"  {axis}: {', '.join(vals)}")
    artifact_vals = enum_values(con, "artifact_required")
    lines.append(
        f"  artifacts_required (zero or more from): {', '.join(artifact_vals)}"
    )
    return "\n".join(lines)


def _load_prompt(con: duckdb.DuckDBPyConnection) -> tuple[str, str]:
    """Load the prompt from disk. If `{{ENUM_VALUES_BLOCK}}` appears in the
    file, substitute it with the live enum values; otherwise assume the
    prompt embeds enums inline already and skip the substitution. Version
    hashes the raw file content alone so swapping enums (without editing
    the prompt) doesn't churn the version."""
    raw = PROMPT_PATH.read_text()
    if ENUM_BLOCK_PLACEHOLDER in raw:
        enum_block = _build_enum_block(con)
        system_prompt = raw.replace(ENUM_BLOCK_PLACEHOLDER, enum_block)
        version_input = raw + enum_block
    else:
        system_prompt = raw
        version_input = raw
    version = "v" + hashlib.sha256(version_input.encode("utf-8")).hexdigest()[:12]
    return system_prompt, version


def _extract_text(body: dict) -> str:
    """Best-effort text extraction across Perplexity Agent API response shapes."""
    if not isinstance(body, dict):
        return json.dumps(body)
    # Anthropic-style messages output (`output: [{type:"message", content:[{text:...}]}]`)
    if "output" in body and isinstance(body["output"], list):
        for item in body["output"]:
            if isinstance(item, dict) and "content" in item:
                for c in item["content"]:
                    if isinstance(c, dict) and c.get("type") in ("output_text", "text"):
                        return c.get("text", "")
    if "output_text" in body:
        return body["output_text"]
    if "text" in body:
        return body["text"]
    # OpenAI/Anthropic chat-completions shape
    if "choices" in body and body["choices"]:
        msg = body["choices"][0].get("message") or {}
        if "content" in msg:
            return msg["content"]
    return json.dumps(body)


def _extract_usage(body: dict) -> tuple[int, int]:
    """Return (input_tokens, output_tokens). Zeros if unavailable."""
    if not isinstance(body, dict):
        return 0, 0
    usage = body.get("usage") or {}
    in_tok = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
    out_tok = usage.get("output_tokens") or usage.get("completion_tokens") or 0
    return int(in_tok), int(out_tok)


def _parse_json(text: str) -> dict:
    text = text.strip()
    # Strip ```json fences if the model added them despite instructions.
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


class Judge:
    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self.system_prompt, self.prompt_version = _load_prompt(con)
        # Cache the legal values for every enum we bind to. The small
        # models routinely confuse axes — emitting `repository_architectural`
        # (a rule_kind value) for rule_cognitive_load, for instance. Without
        # this guard, the INSERT blows up at the DuckDB cast and we lose the
        # whole decision instead of recording it as a parse failure for
        # later debugging.
        self._allowed_per_axis: dict[str, list[str]] = {
            axis: list(enum_values(con, axis)) for axis in TAXONOMY_AXES
        }
        self._allowed_per_axis_set: dict[str, set[str]] = {
            axis: set(vals) for axis, vals in self._allowed_per_axis.items()
        }
        self._allowed_artifacts_list: list[str] = list(enum_values(con, "artifact_required"))
        self._allowed_artifacts: set[str] = set(self._allowed_artifacts_list)
        # Pre-build the JSON schema that Perplexity / Anthropic uses to
        # constrain the model output to only valid enum values per axis.
        # If the API doesn't enforce it, the post-parse validator catches
        # the same failures.
        self._response_schema = self._build_response_schema()
        api_key = os.environ.get("PERPLEXITY_API_KEY")
        if not api_key:
            raise RuntimeError("PERPLEXITY_API_KEY must be set")
        self._client = httpx.Client(
            base_url=PERPLEXITY_BASE,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=60,
        )

    def cancel(self) -> None:
        """Close the underlying HTTP client. Called from another thread to
        interrupt an in-flight `classify()` call — the awaiting request
        raises `httpx.RemoteProtocolError` or `RuntimeError` immediately,
        the caller catches it and aborts the rule without writing a row."""
        try:
            self._client.close()
        except Exception:
            pass

    def _build_response_schema(self) -> dict:
        """A JSON Schema sent as response_format. Anthropic / Perplexity's
        Agent API will use this to constrain the model to valid enum values
        per axis — turning "model returns repository_architectural for
        rule_cognitive_load" from a 30%-of-runs failure into structurally
        impossible. If the upstream silently ignores response_format we fall
        through to the post-parse validator."""
        properties: dict = {}
        for axis in TAXONOMY_AXES:
            properties[axis] = {"type": "string", "enum": self._allowed_per_axis[axis]}
        properties["artifacts_required"] = {
            "type": "array",
            "items": {"type": "string", "enum": self._allowed_artifacts_list},
            "uniqueItems": True,
        }
        properties["confidence"] = {"type": "number", "minimum": 0.0, "maximum": 1.0}
        properties["rationale"] = {"type": "string", "maxLength": 240}
        return {
            "type": "object",
            "properties": properties,
            "required": list(TAXONOMY_AXES) + [
                "artifacts_required",
                "confidence",
                "rationale",
            ],
            "additionalProperties": False,
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    def _call(self, prompt: str) -> tuple[dict, int]:
        t0 = time.time()
        # NB: Perplexity's /v1/agent endpoint does NOT accept response_format
        # (returns 400). Schema enforcement is purely post-parse via
        # _allowed_per_axis_set + retry-with-feedback below.
        resp = self._client.post(
            "/v1/agent",
            json={
                "model": JUDGE_MODEL,
                "input": prompt,
                "max_output_tokens": 512,
            },
        )
        resp.raise_for_status()
        return resp.json(), int((time.time() - t0) * 1000)

    def _build_correction_prompt(self, user: str, bad_text: str, axis_errors: list[str]) -> str:
        """Compose a follow-up that pins down which axes the model fumbled
        and lists each axis's allowed values verbatim. Strongest signal we
        can hand back without retraining."""
        correction = ["Your previous response had invalid axis values:"]
        for err in axis_errors:
            correction.append(f"  - {err}")
        correction.append("")
        correction.append("Reminder of allowed values for the axes you got wrong:")
        for err in axis_errors:
            axis = err.split("=", 1)[0]
            correction.append(f"  {axis}: {', '.join(self._allowed_per_axis[axis])}")
        correction.append("")
        correction.append("Re-classify the rule using ONLY the allowed values for each axis. Return ONLY the corrected JSON object.")
        feedback = "\n".join(correction)
        return (
            f"SYSTEM:\n{self.system_prompt}\n\n"
            f"USER:\n{user}\n\n"
            f"ASSISTANT (your previous reply, which was wrong):\n{bad_text}\n\n"
            f"USER:\n{feedback}"
        )

    def classify(self, rule_text: str, source_kind: str) -> JudgeResult:
        user = f"source_kind: {source_kind}\nrule: {rule_text}"
        prompt = (
            f"SYSTEM:\n{self.system_prompt}\n\n"
            f"USER:\n{user}\n\n"
            "Respond with ONLY the JSON object."
        )
        prompt_messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user},
        ]
        try:
            body, latency_ms = self._call(prompt)
        except Exception as e:
            return JudgeResult(
                label=None,
                prompt_messages=prompt_messages,
                raw_response="",
                parse_ok=False,
                parse_error=f"transport_error: {type(e).__name__}: {e}"[:300],
                latency_ms=0,
                input_tokens=0,
                output_tokens=0,
            )
        text = _extract_text(body)
        input_tokens, output_tokens = _extract_usage(body)
        # Fall back to a rough estimate (1 token ≈ 4 bytes) so budget tracking
        # works even when Perplexity omits usage.
        if input_tokens == 0:
            input_tokens = max(1, len(prompt) // 4)
        if output_tokens == 0:
            output_tokens = max(1, len(text) // 4)
        try:
            obj = _parse_json(text)
            values = {a: obj[a] for a in TAXONOMY_AXES}
            # Validate every axis value against its enum. If the model
            # mixed up axes (e.g. emitted a rule_kind value for cognitive_load),
            # try one corrective re-prompt before giving up. Most of the
            # observed failures are cross-axis bleed (Haiku confusing similar-
            # looking enums) — the model usually fixes them when told exactly
            # which axis it botched and shown the allowed values again.
            axis_errors = [
                f"{axis}={values[axis]!r}"
                for axis in TAXONOMY_AXES
                if values[axis] not in self._allowed_per_axis_set[axis]
            ]
            if axis_errors:
                try:
                    correction = self._build_correction_prompt(user, text, axis_errors)
                    body2, latency_ms2 = self._call(correction)
                    latency_ms += latency_ms2
                    text2 = _extract_text(body2)
                    in_tok2, out_tok2 = _extract_usage(body2)
                    if in_tok2 == 0:
                        in_tok2 = max(1, len(correction) // 4)
                    if out_tok2 == 0:
                        out_tok2 = max(1, len(text2) // 4)
                    input_tokens += in_tok2
                    output_tokens += out_tok2
                    obj2 = _parse_json(text2)
                    values2 = {a: obj2[a] for a in TAXONOMY_AXES}
                    axis_errors2 = [
                        f"{axis}={values2[axis]!r}"
                        for axis in TAXONOMY_AXES
                        if values2[axis] not in self._allowed_per_axis_set[axis]
                    ]
                    if not axis_errors2:
                        # Retry succeeded — use the corrected values.
                        text = text2
                        obj = obj2
                        values = values2
                        axis_errors = []
                except Exception:
                    # Retry blew up (network / JSON / etc.); fall through to
                    # recording the original failure with parse_ok=false.
                    pass
            if axis_errors:
                return JudgeResult(
                    label=None,
                    prompt_messages=prompt_messages,
                    raw_response=text,
                    parse_ok=False,
                    parse_error=("invalid axis values (after retry): " + ", ".join(axis_errors))[:300],
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
            raw_artifacts = [str(a) for a in obj.get("artifacts_required", []) if a]
            cleaned_artifacts = [a for a in raw_artifacts if a in self._allowed_artifacts]
            if len(cleaned_artifacts) != len(raw_artifacts):
                dropped = [a for a in raw_artifacts if a not in self._allowed_artifacts]
                # Soft-fail: drop the bad values and proceed. parse_ok stays
                # True because the classification axes themselves are valid.
                import logging as _logging
                _logging.getLogger("judge").warning(
                    "dropped invalid artifacts_required values: %s", dropped,
                )
            label = JudgeLabel(
                values=values,
                artifacts_required=cleaned_artifacts,
                confidence=float(obj.get("confidence", 0.5)),
                rationale=str(obj.get("rationale", ""))[:500],
            )
            return JudgeResult(
                label=label,
                prompt_messages=prompt_messages,
                raw_response=text,
                parse_ok=True,
                parse_error=None,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            return JudgeResult(
                label=None,
                prompt_messages=prompt_messages,
                raw_response=text,
                parse_ok=False,
                parse_error=f"{type(e).__name__}: {e}"[:300],
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
