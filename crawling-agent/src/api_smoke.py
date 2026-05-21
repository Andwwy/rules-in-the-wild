"""Pre-flight check run once per crawl session.

The admin UI's Start button calls `run()` BEFORE spawning the crawler. The
point is to catch misconfigured keys, wrong model names, and clean-up
regressions of the parsing code (we burned tokens on this last time —
68 rules failed in a row because the judge response shape changed).

Three cheap calls (well under a cent total):
  - embedder: one short string → must return a 1024-d float vector
  - judge: classify a synthetic rule → must return a usable JudgeLabel
  - github: GET /rate_limit → must report enough headroom for the seed
"""

import os
import time
from dataclasses import dataclass

import httpx

from .config import JUDGE_ENABLED
from .db import conn
from .embedder import embed


@dataclass
class SmokeResult:
    ok: bool
    embedder_ms: float | None
    judge_ms: float | None
    github_ms: float | None
    github_remaining: int | None
    errors: list[str]
    warnings: list[str]


def _check_embedder() -> tuple[float, str | None]:
    t0 = time.time()
    try:
        v = embed(["The agent must always read DESIGN.md before editing schema.sql."])
    except Exception as e:
        return (time.time() - t0) * 1000, f"embedder: {e}"
    dt = (time.time() - t0) * 1000
    if not v or len(v) != 1 or len(v[0]) != 1024:
        return dt, f"embedder: wrong shape (got {len(v)} vec(s), dim {len(v[0]) if v else 0})"
    return dt, None


def _check_judge() -> tuple[float | None, str | None]:
    """Skip when the judge is disabled (config.JUDGE_ENABLED=False).
    Returns (None, None) — the UI treats absent timing as 'not checked'."""
    if not JUDGE_ENABLED:
        return None, None
    # Local import so disabling the judge doesn't drag the Judge class through
    # unrelated paths (and so its module can stay slimmer when off).
    from .judge import Judge
    t0 = time.time()
    try:
        with conn() as c:
            j = Judge(c)
            label = j.classify(
                "Always run `cargo test` before committing.",
                "agents_md",
            )
    except Exception as e:
        return (time.time() - t0) * 1000, f"judge: {e}"
    dt = (time.time() - t0) * 1000
    if not label or not label.values.get("enforcement_mechanism"):
        return dt, "judge: response missing enforcement_mechanism"
    return dt, None


def _check_github() -> tuple[float, int | None, str | None]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "rules-prototype/0.1",
    }
    if tok := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {tok}"
    t0 = time.time()
    try:
        r = httpx.get("https://api.github.com/rate_limit", headers=headers, timeout=10)
    except Exception as e:
        return (time.time() - t0) * 1000, None, f"github: {e}"
    dt = (time.time() - t0) * 1000
    if r.status_code != 200:
        return dt, None, f"github: status {r.status_code}"
    core = r.json()["resources"]["core"]
    remaining = int(core["remaining"])
    if remaining < 50:
        return dt, remaining, f"github: only {remaining}/{core['limit']} requests left this hour"
    return dt, remaining, None


def run() -> SmokeResult:
    """Sequential calls (~3 s total). Done synchronously inside the Streamlit
    request — fast enough to feel instant while still proving every keypath."""
    errors: list[str] = []
    warnings: list[str] = []
    embedder_ms, e_err = _check_embedder()
    if e_err:
        errors.append(e_err)
    judge_ms, j_err = _check_judge()
    if j_err:
        errors.append(j_err)
    github_ms, gh_remaining, gh_err = _check_github()
    if gh_err:
        errors.append(gh_err)
    # GITHUB_TOKEN is optional for tree/file seeds but REQUIRED for code_search
    # seeds (Code Search returns 401 without auth). Warn so the user knows the
    # discovery seeds will be skipped silently.
    if not os.environ.get("GITHUB_TOKEN"):
        warnings.append(
            "GITHUB_TOKEN missing — code_search seeds will be skipped "
            "(hand-picked + tree seeds still work)"
        )
    return SmokeResult(
        ok=not errors,
        embedder_ms=embedder_ms,
        judge_ms=judge_ms,
        github_ms=github_ms,
        github_remaining=gh_remaining,
        errors=errors,
        warnings=warnings,
    )
