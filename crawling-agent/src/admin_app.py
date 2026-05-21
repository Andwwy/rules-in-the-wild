"""Streamlit admin UI (DuckDB + threaded crawler edition).

The crawler runs as a Python thread inside this same Streamlit process, not
as a subprocess: DuckDB doesn't support multi-process writers to one file,
and the thread model lets us share an in-memory heartbeat + threading.Event
stop signal cleanly. `st.cache_resource` keeps the CrawlState singleton
across Streamlit reruns and across browser tab opens.

Watchdog model: every Streamlit rerun bumps `state.heartbeat = time.time()`.
The auto-refresh ticks every 5 s while a crawl is running, so closing the
laptop / browser tab freezes the timestamp; the crawler thread sees the
staleness between files and exits with status='partial'.
"""

import threading
import time
from datetime import datetime

import pandas as pd
import pytz
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Display timezone for all human-facing timestamps. DuckDB stores TIMESTAMPTZ
# in UTC; we convert on the way out. `America/New_York` handles DST automatically
# (EST in winter, EDT in summer).
_DISPLAY_TZ = pytz.timezone("America/New_York")


def _fmt_local(dt: datetime | None, fmt: str = "%H:%M:%S %Z") -> str:
    """Convert a UTC datetime from DuckDB to Eastern Time for display."""
    if dt is None:
        return ""
    return dt.astimezone(_DISPLAY_TZ).strftime(fmt)

from src import api_smoke
from src.adapters.github import get_rate_state, is_paused
from src.config import JUDGE_ENABLED
from src.crawl import CrawlState, continuous_loop
from src.db import conn, enum_values, get_setting, set_setting


st.set_page_config(page_title="Rules-in-the-Wild — Prototype", layout="wide")


# ---------------------------------------------------------------------------
# Shared crawl state (one instance for the whole Streamlit process)
# ---------------------------------------------------------------------------

@st.cache_resource
def get_crawl_state() -> CrawlState:
    return CrawlState(
        heartbeat=time.time(),
        stop_event=threading.Event(),
        run_id=None,
        status="idle",
    )


@st.cache_resource
def get_thread_handle() -> dict:
    """Holds the running thread so we can poll is_alive() across reruns."""
    return {"thread": None}


def _start_continuous(state: CrawlState, handle: dict) -> None:
    """Persist `continuous_mode = on` and spawn the loop thread. Idempotent:
    if a thread is already alive we just refresh the setting."""
    with conn() as c:
        set_setting(c, "continuous_mode", "on")
    if handle.get("thread") and handle["thread"].is_alive():
        return
    state.stop_event = threading.Event()
    state.beat()
    state.status = "running"
    state.error = None
    state.last_message = "starting continuous mode"

    t = threading.Thread(
        target=continuous_loop, args=(state,),
        daemon=True, name="crawler-continuous",
    )
    t.start()
    handle["thread"] = t


def _stop_continuous(state: CrawlState) -> None:
    """Persist `continuous_mode = off` and signal the loop to exit. The thread
    will finish its current pass-iteration check and exit cleanly."""
    with conn() as c:
        set_setting(c, "continuous_mode", "off")
    state.stop_event.set()


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_crawl, tab_browse, tab_stats = st.tabs(["Crawl", "Browse", "Stats"])

state = get_crawl_state()
handle = get_thread_handle()
is_running = handle["thread"] is not None and handle["thread"].is_alive()

# Auto-start on boot: if the persisted setting says continuous mode was on,
# and no thread is alive in this process yet, spawn it. This is what makes
# the crawl pick up where it left off across `docker compose restart admin`,
# Streamlit reloads, Ctrl-C, container OOM, etc.
if not is_running:
    with conn() as _c:
        _continuous_persisted = get_setting(_c, "continuous_mode", "off") == "on"
    if _continuous_persisted:
        _start_continuous(state, handle)
        is_running = True


# ---------------------------------------------------------------------------
# Crawl
# ---------------------------------------------------------------------------
with tab_crawl:
    st.header("Crawl the open internet")
    from src.crawl import PASS_INTERVAL_SECONDS, SKIP_RECENT_HOURS
    _secs = int(PASS_INTERVAL_SECONDS)
    _interval = f"{_secs} s" if _secs < 60 else f"{_secs // 60} min"
    st.caption(
        "Discovers trending agent projects across public GitHub via the search API — "
        "`/search/repositories` on topics like `agents`, `agentic-ai`, `cursor-rules`, "
        "`claude-code`, plus direct `path:AGENTS.md` / `CLAUDE.md` / `.cursorrules` "
        f"file searches. Re-runs every {_interval}; repos crawled in the past "
        f"{SKIP_RECENT_HOURS} h are skipped so each pass focuses on new content. "
        "Closing this tab does not stop the crawl; closing or sleeping the laptop "
        "suspends the process and it picks up where it left off on wake. The "
        "continuous-mode toggle is persisted in DuckDB, so it also resumes across "
        "admin restarts."
    )

    if is_running:
        st.button("Stop", on_click=_stop_continuous, args=(state,), use_container_width=True)
        st.info(state.last_message or "Continuous crawl running.")
        # Bump heartbeat each rerun (used only for in-UI 'last seen' display
        # now — no longer aborts the worker). Auto-refresh so the panel below
        # ticks while a pass is mid-flight.
        state.beat()
        st_autorefresh(interval=5000, key="crawl_refresh")
    else:
        if st.button("Start continuous crawl", type="primary", use_container_width=True):
            with st.spinner("Pre-flight: testing embedder, judge, GitHub…"):
                result = api_smoke.run()
            if not result.ok:
                st.error("Pre-flight failed — not starting crawl.")
                for e in result.errors:
                    st.error(f"  • {e}")
            else:
                judge_part = f"judge {result.judge_ms:.0f} ms · " if result.judge_ms is not None else "judge disabled · "
                st.success(
                    f"Pre-flight OK · embedder {result.embedder_ms:.0f} ms · "
                    f"{judge_part}"
                    f"GitHub {result.github_ms:.0f} ms ({result.github_remaining} req left)"
                )
                for w in result.warnings:
                    st.warning(f"  • {w}")
                _start_continuous(state, handle)
                st.rerun()

    # Cumulative dashboard — corpus totals + worker status.
    st.divider()
    st.subheader("Corpus")

    with conn() as c:
        files, rules = c.execute(
            """
            SELECT
                (SELECT count(*) FROM rules_file),
                (SELECT count(*) FROM rule)
            """
        ).fetchone()
        last = c.execute(
            """
            SELECT id, COALESCE(finished_at, started_at), error_message
              FROM ingestion_run
             ORDER BY started_at DESC
             LIMIT 1
            """
        ).fetchone()
    last_run_id = last[0] if last else None
    last_activity = last[1] if last else None
    last_pass_error = last[2] if last else None

    def _format_ago(when):
        if when is None:
            return "—"
        delta = (datetime.now(_DISPLAY_TZ) - when.astimezone(_DISPLAY_TZ)).total_seconds()
        if delta < 5:
            return "just now"
        if delta < 90:
            return f"{int(delta)}s ago"
        if delta < 3600:
            return f"{int(delta / 60)}m ago"
        if delta < 86400:
            return f"{int(delta / 3600)}h ago"
        return f"{int(delta / 86400)}d ago"

    # Three-state status:
    #   - 🟢 running          : thread alive and actively making API calls
    #   - 🟡 waiting limit    : thread alive but blocked in _maybe_pause_for_rate
    #   - ⚪ stopped          : thread not alive
    paused_now, paused_bucket, paused_resets_at = is_paused()
    if is_running and paused_now:
        wait_left = max(0, paused_resets_at - int(time.time()))
        wait_str = f"{wait_left // 60}m {wait_left % 60}s" if wait_left >= 60 else f"{wait_left}s"
        status_metric = "🟡 waiting limit"
        status_help = f"{paused_bucket} bucket exhausted; resumes in {wait_str}"
    elif is_running:
        status_metric = "🟢 running"
        status_help = None
    else:
        status_metric = "⚪ stopped"
        status_help = None

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Status", status_metric, help=status_help)
    m2.metric("Files", int(files or 0))
    m3.metric("Rules", int(rules or 0))
    m4.metric("Last activity", _format_ago(last_activity))

    # Below the metrics: a small caption with what the worker is doing right
    # now (when running) OR what the most recent pass produced (when stopped).
    if is_running and state.last_message:
        st.caption(f"Working on: `{state.last_message}`")
    if last_pass_error and not is_running:
        st.caption(f"Note from last pass: {last_pass_error}")

    # ---- GitHub API budget ----
    # Updated after every GitHub request via response headers. When a bucket
    # hits zero, the crawler pauses until reset_at; we render a yellow banner
    # with the countdown so the user knows what's happening.
    rate = get_rate_state()
    if rate:
        # Show core + search side-by-side. Order them deterministically.
        ordered = sorted(rate.items(), key=lambda kv: kv[0])
        cols = st.columns(len(ordered))
        now_ts = int(time.time())
        any_exhausted = False
        for col, (bucket, entry) in zip(cols, ordered):
            remaining = entry["remaining"]
            limit = entry["limit"]
            reset_in = max(0, entry["reset_at"] - now_ts)
            if reset_in >= 60:
                reset_str = f"{reset_in // 60}m {reset_in % 60}s"
            else:
                reset_str = f"{reset_in}s"
            if remaining == 0 and reset_in > 0:
                any_exhausted = True
            col.metric(
                f"GitHub {bucket}",
                f"{remaining}/{limit}",
                help=f"Resets in {reset_str}",
            )
            col.caption(f"Resets in {reset_str}")
        if paused_now:
            wait_left = max(0, paused_resets_at - int(time.time()))
            wait_str = f"{wait_left // 60}m {wait_left % 60}s" if wait_left >= 60 else f"{wait_left}s"
            st.warning(
                f"🟡 Waiting on GitHub limit reset — `{paused_bucket}` bucket "
                f"exhausted, resumes in {wait_str}. Stop is responsive during the pause."
            )
        elif any_exhausted:
            st.caption(
                "A GitHub bucket is at zero but no thread is currently paused — "
                "the next API call will trigger a pause."
            )

    # Recent events (still scoped to the most recent run row for diagnostics).
    if last_run_id:
        with conn() as c:
            events = c.execute(
                """
                SELECT event_at, level, message
                  FROM ingestion_event
                 WHERE run_id = ?
                 ORDER BY event_at DESC
                 LIMIT 15
                """,
                [last_run_id],
            ).fetchall()
        if events:
            with st.expander("Recent events (latest pass)", expanded=False):
                for event_at, level, message in events:
                    st.text(f"{_fmt_local(event_at)}  [{level}]  {message}")


# ---------------------------------------------------------------------------
# Browse
# ---------------------------------------------------------------------------
with tab_browse:
    st.header("Browse rules")
    with conn() as c:
        enforce_vals = enum_values(c, "enforcement_mechanism")
        kind_vals = enum_values(c, "rules_file_kind")
        total_rules = c.execute("SELECT count(*) FROM rule").fetchone()[0]
        projects = [r[0] for r in c.execute(
            """
            SELECT DISTINCT sp.owner || '/' || sp.name AS proj
              FROM source_project sp
              JOIN rules_file sf ON sf.project_id = sp.id
             WHERE EXISTS (SELECT 1 FROM rule r WHERE r.rules_file_id = sf.id)
             ORDER BY proj
            """
        ).fetchall()]

    # Filter row. The enforcement_mechanism filter only shows when the judge is
    # on — when it's off, every row's value is NULL and the filter is a no-op.
    if JUDGE_ENABLED:
        c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
        em_filter = c1.multiselect("enforcement_mechanism", enforce_vals)
        sk_filter = c2.multiselect("source_kind", kind_vals)
        proj_filter = c3.multiselect("project", projects)
        text_q = c4.text_input("search text", placeholder="substring match (ILIKE)")
    else:
        em_filter = []
        c1, c2, c3 = st.columns([2, 2, 3])
        sk_filter = c1.multiselect("source_kind", kind_vals)
        proj_filter = c2.multiselect("project", projects)
        text_q = c3.text_input("search text", placeholder="substring match (ILIKE)")

    wheres = ["TRUE"]
    params: list = []
    if em_filter:
        wheres.append("ll.enforcement_mechanism = ANY(?)")
        params.append(em_filter)
    if sk_filter:
        wheres.append("sf.kind = ANY(?)")
        params.append(sk_filter)
    if proj_filter:
        wheres.append("(sp.owner || '/' || sp.name) = ANY(?)")
        params.append(proj_filter)
    if text_q:
        wheres.append("r.rule_text ILIKE ?")
        params.append(f"%{text_q}%")

    LIMIT = 500
    # `rule_llm_decision` is append-only (multiple rows per rule); take the
    # latest parsed-OK decision per rule. The view `rule_classification_current`
    # exists for the human-override-aware version but doesn't expose
    # confidence/rationale, which the Browse expander shows.
    query = f"""
        SELECT r.rule_text, r.section_anchor, r.line_start, r.line_end,
               sf.kind, sp.canonical_url, sf.path, sf.commit_sha,
               sp.owner || '/' || sp.name AS project,
               ll.specificity, ll.cognitive_load, ll.constraint_level,
               ll.enforcement_mechanism, ll.enforcement_scope,
               ll.enforcement_trigger, ll.rule_kind,
               ll.artifacts_required, ll.confidence, ll.rationale
          FROM rule r
          JOIN rules_file sf  ON sf.id = r.rules_file_id
          JOIN source_project sp ON sp.id = sf.project_id
          LEFT JOIN (
              SELECT rule_id, specificity, cognitive_load, constraint_level,
                     enforcement_mechanism, enforcement_scope, enforcement_trigger,
                     rule_kind, artifacts_required, confidence, rationale,
                     ROW_NUMBER() OVER (PARTITION BY rule_id ORDER BY created_at DESC) AS rn
                FROM rule_llm_decision
               WHERE parse_ok = TRUE
          ) ll ON ll.rule_id = r.id AND ll.rn = 1
         WHERE {' AND '.join(wheres)}
         ORDER BY r.extracted_at DESC
         LIMIT {LIMIT}
    """
    with conn() as c:
        rows = c.execute(query, params).fetchall()

    # Caption with both filtered and total counts so user has scale context.
    if total_rules == 0:
        st.caption("Corpus is empty — Start a crawl on the Crawl tab.")
    elif len(rows) == total_rules:
        st.caption(f"{total_rules} rules — click to expand")
    elif len(rows) >= LIMIT:
        st.caption(
            f"Showing first {LIMIT} of {total_rules:,} rules (filtered) — "
            f"narrow with filters above to see specific items."
        )
    else:
        st.caption(f"{len(rows):,} of {total_rules:,} rules match — click to expand")

    for (text, anchor, lstart, lend, skind, repo, path, commit, project,
         spec, cload, clevel, mech, scope, trigger, rkind,
         artifacts, conf, rationale) in rows:
        with st.expander(text):
            permalink = f"{repo}/blob/{commit}/{path}#L{lstart}-L{lend}" if commit else None
            # Layout depends on whether we have anything to show in the right column.
            if JUDGE_ENABLED:
                left, right = st.columns(2)
            else:
                left, right = st.container(), None
            with left:
                st.markdown(f"**Project** `{project}`  ·  **Source kind** `{skind}`")
                if permalink:
                    st.markdown(f"**Permalink** [{path}:L{lstart}-L{lend}]({permalink})")
                else:
                    st.markdown(f"**Path** `{path}:L{lstart}-L{lend}`")
                if anchor:
                    st.markdown(f"**Section** `{anchor}`")
                if conf is not None:
                    st.markdown(f"**Judge confidence** `{conf:.2f}`")
            if right is not None:
                with right:
                    st.markdown(f"**Enforcement mechanism** `{mech or '—'}`")
                    st.markdown(f"**Enforcement trigger** `{trigger or '—'}`")
                    st.markdown(f"**Enforcement scope** `{scope or '—'}`")
                    st.markdown(f"**Rule kind** `{rkind or '—'}`")
                    st.markdown(f"**Specificity** `{spec or '—'}`")
                    st.markdown(f"**Cognitive load** `{cload or '—'}`")
                    st.markdown(f"**Constraint level** `{clevel or '—'}`")
                    if artifacts:
                        st.markdown(f"**Artifacts required** `{', '.join(artifacts)}`")
            if rationale:
                st.caption(f"Judge rationale: {rationale}")


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
with tab_stats:
    st.header("Row counts")
    with conn() as c:
        rows = []
        for tbl in ("source_project", "rules_file", "rule",
                    "rule_llm_decision", "rule_human_label",
                    "ingestion_run", "ingestion_event"):
            count = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            rows.append({"table": tbl, "count": count})
        st.table(pd.DataFrame(rows))
