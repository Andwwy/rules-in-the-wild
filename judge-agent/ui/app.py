"""Streamlit dashboard for the judge agent.

Mirrors the prototype's admin_app.py visual style: wide layout, four-metric
header, st_autorefresh ticker, divider-separated sections, "Working on…"
caption, metric chips with help tooltips. UI is HTTP-only — it speaks to
`judge` (the FastAPI worker container) via its REST endpoints. No DB access
from this process so we don't fight DuckDB connection-thread rules.
"""

from __future__ import annotations

import os
import time
from typing import Any

import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh


JUDGE_API = os.environ.get("JUDGE_API_URL", "http://judge:8000").rstrip("/")
REFRESH_MS = 1500


st.set_page_config(page_title="Judge Agent — Prototype", layout="wide")


# ---------------------------------------------------------------------------
# Tiny HTTP helpers — short timeouts so the UI is responsive even when the
# worker is mid-call (~1.5 s per Perplexity request).
# ---------------------------------------------------------------------------

def _get_state() -> dict[str, Any] | None:
    try:
        r = requests.get(f"{JUDGE_API}/api/state", timeout=2)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Cannot reach judge API at {JUDGE_API}: {e}")
        return None


def _post(path: str, json: dict[str, Any] | None = None) -> dict[str, Any] | None:
    try:
        r = requests.post(f"{JUDGE_API}{path}", json=json, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"POST {path} failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Header + auto-refresh
# ---------------------------------------------------------------------------

st.title("Judge agent")
st.caption(
    "Classifies extracted rules along the v0.3 taxonomy via Perplexity-routed "
    "Haiku 4.5. Reads `rule` rows that have no `parse_ok=true` row in "
    "`rule_llm_decision` yet, judges them in batches of 20 every 30 s, and "
    "stops when the spending cap is reached. Stop is instant — any in-flight "
    "Perplexity request is cancelled and the rule stays unjudged. The cap "
    "and accumulated spend persist in `crawl_settings` across container restarts."
)

state = _get_state()
if state is None:
    st.stop()

# Refresh more aggressively while running so the "current rule" panel feels
# live; slower at idle.
st_autorefresh(
    interval=REFRESH_MS if state["status"] != "idle" else REFRESH_MS * 3,
    key="judge_refresh",
)


# ---------------------------------------------------------------------------
# Start / Stop controls
# ---------------------------------------------------------------------------

is_running = state["status"] == "running"
is_stopping = state["status"] == "stopping"

if is_running:
    if st.button("Stop", use_container_width=True):
        _post("/api/stop")
        st.rerun()
elif is_stopping:
    st.info("Stopping… (any in-flight inference is being cancelled)")
else:
    if st.button("Start judging", type="primary", use_container_width=True):
        _post("/api/start")
        st.rerun()

if state.get("error"):
    st.error(state["error"])


# ---------------------------------------------------------------------------
# Status + counters (mirrors the prototype's 4-metric row)
# ---------------------------------------------------------------------------

status_map = {
    "running": ("🟢 running", "worker is judging rules"),
    "stopping": ("🟡 stopping", "in-flight call being dropped"),
    "idle": ("⚪ stopped", None),
}
status_metric, status_help = status_map.get(state["status"], ("⚪ stopped", None))

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Status", status_metric, help=status_help)
m2.metric(
    "Judged",
    int(state.get("total_judged", 0)),
    help="Rules recorded with parse_ok=true — usable as labels",
)
m3.metric(
    "Parse failed",
    int(state.get("total_parse_failed", 0)),
    help=(
        "Rules where Perplexity returned text but it wasn't a valid "
        "classification (e.g. axis values from the wrong enum, malformed "
        "JSON, missing key). Recorded in rule_llm_decision with parse_ok=false "
        "so the raw response is preserved for prompt debugging."
    ),
)
m4.metric(
    "Infra failed",
    int(state.get("total_failed", 0)),
    help="Network or DB errors — no row was written for these rules",
)
m5.metric(
    "Last activity",
    "—" if not (state.get("started_at") or state.get("stopped_at")) else (
        time.strftime(
            "%H:%M:%S",
            time.localtime(state.get("stopped_at") or state.get("started_at") or 0),
        )
    ),
)

# Below the metrics: small caption with what the worker is doing right now.
if is_running and state.get("current_rule"):
    cur = state["current_rule"]
    st.caption(
        f"Working on: `{cur['source_path']}` "
        f"(lines {cur['start_line']}–{cur['end_line']}) — "
        f"`{cur['rule_text'][:80]}{'…' if len(cur['rule_text']) > 80 else ''}`"
    )


# ---------------------------------------------------------------------------
# Spending cap + persistent spend meter
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Spending")

spent = float(state.get("spent_usd", 0.0))
cap = float(state.get("max_usd", 0.0))
pct = (spent / cap * 100) if cap > 0 else 0.0

s1, s2, s3 = st.columns([2, 1, 1])
s1.metric("Spent", f"${spent:.4f}", help="Persisted in crawl_settings.judge_spend_usd")
s2.metric("Cap", f"${cap:.4f}")
s3.metric("% of cap", f"{pct:.1f}%", delta=None if pct < 60 else f"{pct - 60:.1f}% over warn")

st.progress(min(1.0, pct / 100.0) if cap > 0 else 0.0)

c1, c2, c3 = st.columns([2, 1, 1])
new_cap = c1.number_input(
    "Set new cap (USD)",
    min_value=0.0,
    max_value=1000.0,
    value=float(cap or 1.0),
    step=0.50,
    format="%.4f",
    help="Persists to crawl_settings.judge_max_usd; survives container restarts.",
)
if c2.button("Update cap", use_container_width=True):
    _post("/api/cap", {"max_usd": new_cap})
    st.rerun()
if c3.button("Reset spend", use_container_width=True, help="Clears crawl_settings.judge_spend_usd"):
    _post("/api/reset-spend")
    st.rerun()


# ---------------------------------------------------------------------------
# Current rule — source-file viewer with highlight
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Current rule")

cur = state.get("current_rule")
if not cur:
    st.caption("No rule in flight. Start the worker to see rules stream by here.")
else:
    info_cols = st.columns([2, 1, 1])
    info_cols[0].markdown(f"**Source:** `{cur['source_path']}`")
    info_cols[1].markdown(f"**Lines:** {cur['start_line']}–{cur['end_line']}")
    info_cols[2].markdown(f"**Kind:** `{cur['source_kind']}`")

    st.markdown("**Rule text**")
    st.code(cur["rule_text"], language="markdown")

    st.markdown("**In context (highlighted lines = the rule)**")
    # Build a single block of monospace text with a leading `>` marker on
    # highlighted lines so they pop in st.code.
    lines = cur.get("source_lines") or []
    if lines:
        width = max(2, len(str(max(l["line_number"] for l in lines))))
        rendered = []
        for l in lines:
            marker = "▶" if l["highlighted"] else " "
            rendered.append(f"{marker} {str(l['line_number']).rjust(width)} │ {l['text']}")
        st.code("\n".join(rendered), language="text")
    else:
        st.caption("(no source context available)")


# ---------------------------------------------------------------------------
# Recent results — table view
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Recent decisions")

recent = state.get("recent") or []
if not recent:
    st.caption("No decisions yet this session.")
else:
    rows = []
    for r in recent:
        values = r.get("values") or {}
        # On parse failures, surface the reason inline (in the rule column we
        # have spare horizontal space, and axis cells are blank anyway).
        if not r["parse_ok"]:
            rule_text = r["rule_text"][:60] + ("…" if len(r["rule_text"]) > 60 else "")
            err = r.get("parse_error") or "(no error message)"
            rule_cell = f"{rule_text}\n⚠ {err}"
        else:
            rule_cell = r["rule_text"][:100] + ("…" if len(r["rule_text"]) > 100 else "")
        rows.append({
            "parse": "✓" if r["parse_ok"] else "✗",
            "rule / parse_error": rule_cell,
            "source": r["source_path"],
            "spec": values.get("rule_specificity", "—"),
            "cog": values.get("rule_cognitive_load", "—"),
            "constr": values.get("rule_constraint_level", "—"),
            "mech": values.get("enforcement_mechanism", "—"),
            "scope": values.get("enforcement_scope", "—"),
            "trig": values.get("enforcement_trigger", "—"),
            "kind": values.get("rule_kind", "—"),
            "conf": (round(r["confidence"], 2) if r.get("confidence") is not None else None),
            "ms": r["latency_ms"],
            "$": f"${r['cost_usd']:.5f}",
        })
    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=380,
        column_config={
            "rule / parse_error": st.column_config.TextColumn(
                "rule / parse_error",
                width="large",
                help="Rule text on top; on parse failure, the validator's error message is shown after the ⚠.",
            ),
        },
    )


# ---------------------------------------------------------------------------
# Footer — model / prompt version (small, like the prototype's caption rows)
# ---------------------------------------------------------------------------

st.divider()
f1, f2, f3 = st.columns(3)
f1.caption(f"Model: `{state.get('model') or '—'}`")
f2.caption(f"Prompt version: `{state.get('prompt_version') or '—'}`")
f3.caption(f"API: `{JUDGE_API}`")
