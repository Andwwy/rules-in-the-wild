"""Crawl pipeline (DuckDB edition, open-internet discovery).

Two entry points:

  1. CLI:
       python -m src.crawl              # one discovery pass
       python -m src.crawl --cluster    # dedup pass
       python -m src.crawl --stats      # row counts

  2. Library (used by the admin UI thread runner):
       continuous_loop(state) — see admin_app.py `_start_continuous()`.

Discovery shape:
  Instead of a fixed `seeds.yaml` (which made every pass re-process the same
  three repos), each pass now queries GitHub's `/search/repositories` and
  `/search/code` endpoints with a handful of agent-related queries. Repos
  whose `source_project.last_crawled_at` is within SKIP_RECENT_HOURS are
  skipped so passes naturally explore new content as GitHub's trending sets
  shift.

State object (used by thread mode):
  - state.heartbeat   : float, mtime-style timestamp the UI bumps every rerun.
  - state.stop_event  : threading.Event(), set by the Stop button.
  - state.run_id      : UUID of the current ingestion_run row.
  - state.files_done / state.rules_new : cumulative counters across passes.

Error handling: each discovery query runs inside its own try/except so one
bad query (transient HTTP error, malformed search term) doesn't poison the
pass. Per-query errors are written as `ingestion_event(level='error', …)`
and the pass continues.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from typing import Iterator

import click
import duckdb

from .adapters.base import FetchedFile
from .adapters.claude_marketplace import (
    discover_solo_plugins_via_code_search,
    discover_via_code_search as discover_marketplaces_via_code_search,
    discover_via_topic_search as discover_marketplaces_via_topic_search,
)
from .adapters.github import (
    _code_search,
    _fetch_one,
    _search_repos,
    set_stop_event as set_github_stop_event,
)
from .config import JUDGE_ENABLED  # noqa: F401  (re-exported elsewhere)
from .db import conn
from .embedder import embed_batched
from .extractor import extract


CRAWLER_VERSION = "proto-0.4-trending"

# Continuous-mode pass interval. The loop sleeps this long between passes.
# Set short for visible progress; ADR-001 §Decision uses an hourly Lambda in
# production. At <300 sec, a pass may take longer than the interval itself,
# in which case passes run back-to-back with no idle gap.
PASS_INTERVAL_SECONDS = 60

# How often the continuous loop wakes to check stop_event between passes.
POLL_INTERVAL_SECONDS = 5.0

# Don't re-crawl a repo whose source_project.last_crawled_at is within this
# window. Keeps each pass focused on NEW content as GitHub's trending set
# rotates, instead of repeating the same repos every minute.
SKIP_RECENT_HOURS = 24

# Per-query cap on how many repos to fetch from /search/repositories. Tune
# down to lower rate-limit pressure; tune up for more coverage per pass.
MAX_REPOS_PER_QUERY = 25
MAX_FILES_PER_CODE_QUERY = 25

# Discovery queries — what counts as "agent rule files across the open internet".
# Each entry is (kind, query, paths_or_none, source_kind):
#   - kind="repo": runs /search/repositories(q=query); for each returned repo,
#                  probe each path in `paths` and yield a FetchedFile if found.
#   - kind="code": runs /search/code(q=query); each result is already
#                  (repo, path) so `paths` is None.
# `sort:updated-desc` makes GitHub return the most recently active repos so
# the trending set rotates naturally as people push commits.
_DISCOVERY_QUERIES: list[tuple[str, str, tuple[str, ...] | None, str]] = [
    # Trending repos by topic — agent-coded projects in current development.
    ("repo", "topic:agents pushed:>2026-04-01 stars:>10 sort:updated",
     ("AGENTS.md", "CLAUDE.md", ".cursorrules"), "agents_md"),
    ("repo", "topic:agentic-ai stars:>20 sort:updated",
     ("AGENTS.md", "CLAUDE.md", ".cursorrules"), "agents_md"),
    ("repo", "topic:llm-agent stars:>10 sort:updated",
     ("AGENTS.md", "CLAUDE.md", ".cursorrules"), "agents_md"),
    ("repo", "topic:cursor-rules sort:updated", (".cursorrules",), "cursor_rules"),
    ("repo", "topic:claude-code sort:updated", ("CLAUDE.md", "AGENTS.md"), "claude_md"),
    ("repo", "topic:ai-agent pushed:>2026-04-01 stars:>50 sort:updated",
     ("AGENTS.md", "CLAUDE.md", ".cursorrules"), "agents_md"),
    # Direct file finds via Code Search — catches projects that don't tag the
    # topic but do have the canonical filename.
    ("code", "path:AGENTS.md stars:>50", None, "agents_md"),
    ("code", "path:CLAUDE.md stars:>50", None, "claude_md"),
    ("code", "path:.cursorrules stars:>20", None, "cursor_rules"),
    # Claude Code marketplaces and solo plugins — fully trending-driven (no
    # fixed seed list). `sort:updated` rotates the result set each pass; the
    # adapter applies its own per-plugin 24h skip on top of the per-repo skip
    # so individual plugins within an already-known marketplace also rotate.
    ("marketplace_code", "path:.claude-plugin/marketplace.json sort:updated",
     None, None),
    ("solo_plugin_code", "path:.claude-plugin/plugin.json stars:>3 sort:updated",
     None, None),
    ("marketplace_topic", "topic:claude-code-plugin sort:updated", None, None),
    ("marketplace_topic", "topic:claude-marketplace stars:>5 sort:updated", None, None),
    ("marketplace_topic", "topic:claude-skills sort:updated", None, None),
]


# -----------------------------------------------------------------------------
# CrawlState — the small object the admin thread shares with this module
# -----------------------------------------------------------------------------

@dataclasses.dataclass
class CrawlState:
    """Owned by admin_app.get_crawl_state(); passed into the loop."""
    heartbeat: float
    stop_event: threading.Event
    run_id: str | None = None
    status: str = "idle"
    error: str | None = None
    files_done: int = 0
    rules_new: int = 0
    last_message: str = ""

    def beat(self) -> None:
        self.heartbeat = time.time()


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _sha256(s: str) -> bytes:
    return hashlib.sha256(s.encode("utf-8")).digest()


def _event(c: duckdb.DuckDBPyConnection, run_id: str | None,
           level: str, message: str, payload: dict | None = None) -> None:
    if run_id is None:
        return
    c.execute(
        """
        INSERT INTO ingestion_event (id, run_id, level, message, payload)
        VALUES (nextval('ingestion_event_id_seq'), ?, ?, ?, ?)
        """,
        [run_id, level, message, json.dumps(payload) if payload else None],
    )


def _stop_requested(state: CrawlState | None) -> bool:
    return bool(state and state.stop_event.is_set())


# Kinds that are stored as evidence (manifest, hook config) but never run
# through the extractor — they're declarative JSON, no rule text to mine.
_NON_EXTRACTABLE_KINDS = frozenset({
    "claude_marketplace_manifest",
    "claude_plugin_manifest",
    "claude_plugin_hook_config",
})


def _maybe_yield(ff: FetchedFile, seen: set) -> Iterator[FetchedFile]:
    """Dedup wrapper used by marketplace-style discovery branches. Yields the
    FetchedFile iff (owner, repo, path) hasn't already been seen this pass."""
    key = (ff.project_owner, ff.project_name, ff.file_path)
    if key in seen:
        return
    seen.add(key)
    yield ff


def _is_recently_crawled(c: duckdb.DuckDBPyConnection,
                         owner: str, name: str,
                         hours: float = SKIP_RECENT_HOURS) -> bool:
    row = c.execute(
        """
        SELECT last_crawled_at
          FROM source_project
         WHERE host = 'github.com' AND owner = ? AND name = ?
        """,
        [owner, name],
    ).fetchone()
    if not row or row[0] is None:
        return False
    age_h = (datetime.now(timezone.utc) - row[0]).total_seconds() / 3600
    return age_h < hours


# -----------------------------------------------------------------------------
# Source-file plumbing
# -----------------------------------------------------------------------------

def _upsert_project(c: duckdb.DuckDBPyConnection, ff: FetchedFile) -> str:
    row = c.execute(
        "SELECT id FROM source_project WHERE canonical_url = ?",
        [ff.project_canonical_url],
    ).fetchone()
    if row:
        c.execute(
            "UPDATE source_project SET last_crawled_at = now() WHERE id = ?",
            [row[0]],
        )
        return row[0]
    c.execute(
        """
        INSERT INTO source_project (host, owner, name, canonical_url, last_crawled_at)
        VALUES (?, ?, ?, ?, now())
        RETURNING id
        """,
        [ff.project_host, ff.project_owner, ff.project_name, ff.project_canonical_url],
    )
    return c.fetchone()[0]


def _upsert_rules_file(c: duckdb.DuckDBPyConnection, project_id: str,
                       ff: FetchedFile) -> tuple[str, bool]:
    raw_bytes = ff.raw_content.encode("utf-8")
    content_hash = _sha256(ff.raw_content)
    existing = c.execute(
        """
        SELECT id FROM rules_file
         WHERE project_id = ? AND path = ?
           AND (commit_sha = ? OR (commit_sha IS NULL AND ? IS NULL))
        """,
        [project_id, ff.file_path, ff.commit_sha, ff.commit_sha],
    ).fetchone()
    if existing:
        return existing[0], False
    c.execute(
        """
        INSERT INTO rules_file (project_id, path, kind, commit_sha,
                                raw_content, content_sha256, byte_size)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        RETURNING id
        """,
        [project_id, ff.file_path, ff.source_kind, ff.commit_sha,
         ff.raw_content, content_hash, len(raw_bytes)],
    )
    new_id = c.fetchone()[0]
    # New-commit-of-same-file used to flip the old row's is_current=FALSE.
    # `is_current` is no longer in the schema; old rows just remain as
    # historical records, distinguished from the new one by commit_sha.
    return new_id, True


def _process_file(c: duckdb.DuckDBPyConnection, ff: FetchedFile,
                  run_id: str | None, state: CrawlState | None) -> int:
    """Insert project + rules_file + rules. Returns count of NEW rules inserted."""
    project_id = _upsert_project(c, ff)
    rules_file_id, is_new = _upsert_rules_file(c, project_id, ff)
    if state:
        state.files_done += 1
        state.last_message = f"{ff.project_owner}/{ff.project_name}:{ff.file_path}"
    if not is_new:
        return 0
    # Manifest / hook-config rows are stored as evidence only; nothing to extract.
    if ff.source_kind in _NON_EXTRACTABLE_KINDS:
        print(f"[crawl] {ff.project_owner}/{ff.project_name}:{ff.file_path}  (manifest, no extract)")
        return 0
    extracted = extract(ff.raw_content, kind=ff.source_kind)
    if not extracted:
        return 0
    vectors = embed_batched([e.text for e in extracted])
    file_inserted = 0
    for er, vec in zip(extracted, vectors):
        norm = _norm(er.text)
        inserted_row = c.execute(
            """
            INSERT INTO rule (rules_file_id, rule_text, rule_text_norm,
                              rule_text_sha256, section_anchor,
                              line_start, line_end, embedding,
                              extractor_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (rules_file_id, line_start, line_end) DO NOTHING
            RETURNING id
            """,
            [rules_file_id, er.text, norm, _sha256(norm),
             er.section_anchor, er.line_start, er.line_end, vec,
             CRAWLER_VERSION],
        ).fetchone()
        if inserted_row is None:
            continue
        file_inserted += 1
        # Judge call intentionally gated; see config.JUDGE_ENABLED.

    if state:
        state.rules_new += file_inserted
    print(f"[crawl] {ff.project_owner}/{ff.project_name}:{ff.file_path}  +{file_inserted} rules")
    _event(
        c, run_id, "info",
        f"file_done: {ff.project_owner}/{ff.project_name} · {ff.file_path}",
        {"project": f"{ff.project_owner}/{ff.project_name}",
         "path": ff.file_path,
         "inserted": file_inserted},
    )
    return file_inserted


# -----------------------------------------------------------------------------
# Discovery — yields FetchedFile from the open internet
# -----------------------------------------------------------------------------

def _discover_open_internet(c: duckdb.DuckDBPyConnection,
                            state: CrawlState | None,
                            run_id: str | None) -> Iterator[FetchedFile]:
    """Iterate the trending queries, yield candidate files. Skips repos crawled
    in the last SKIP_RECENT_HOURS and dedupes (owner, repo, path) within a pass."""
    seen: set[tuple[str, str, str]] = set()
    for kind, query, paths, source_kind in _DISCOVERY_QUERIES:
        if _stop_requested(state):
            return
        if state:
            state.last_message = f"discover ({kind}): {query[:60]}"
        _event(c, run_id, "info", f"discover_start ({kind}): {query}", {"query": query})
        try:
            if kind == "repo":
                items = _search_repos(query, max_results=MAX_REPOS_PER_QUERY)
                for r in items:
                    if _stop_requested(state):
                        return
                    owner = r["owner"]["login"]
                    name = r["name"]
                    if _is_recently_crawled(c, owner, name):
                        continue
                    for path in (paths or ()):
                        key = (owner, name, path)
                        if key in seen:
                            continue
                        seen.add(key)
                        ff = _fetch_one(owner, name, path, source_kind)
                        if ff:
                            yield ff
            elif kind == "code":
                for ff in _code_search(query, source_kind, MAX_FILES_PER_CODE_QUERY):
                    if _stop_requested(state):
                        return
                    key = (ff.project_owner, ff.project_name, ff.file_path)
                    if key in seen:
                        continue
                    seen.add(key)
                    if _is_recently_crawled(c, ff.project_owner, ff.project_name):
                        continue
                    yield ff
            elif kind == "marketplace_code":
                for ff in discover_marketplaces_via_code_search(
                    c, query, MAX_FILES_PER_CODE_QUERY
                ):
                    if _stop_requested(state):
                        return
                    yield from _maybe_yield(ff, seen)
            elif kind == "solo_plugin_code":
                for ff in discover_solo_plugins_via_code_search(
                    c, query, MAX_FILES_PER_CODE_QUERY
                ):
                    if _stop_requested(state):
                        return
                    yield from _maybe_yield(ff, seen)
            elif kind == "marketplace_topic":
                for ff in discover_marketplaces_via_topic_search(
                    c, query, MAX_REPOS_PER_QUERY
                ):
                    if _stop_requested(state):
                        return
                    yield from _maybe_yield(ff, seen)
            else:
                raise ValueError(f"unknown discovery kind: {kind}")
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            print(f"[discover] query {query!r} failed: {msg}", file=sys.stderr)
            traceback.print_exc()
            _event(
                c, run_id, "error",
                f"discover_failed ({kind}): {query[:80]} — {type(e).__name__}",
                {"query": query, "error": msg},
            )


# -----------------------------------------------------------------------------
# Run one pass
# -----------------------------------------------------------------------------

def run_one_pass(state: CrawlState | None = None) -> None:
    """One pass = one discovery sweep + per-file ingest. Creates its own
    ingestion_run row, updates progress, finalises status on exit."""
    total_files = 0
    total_rules = 0
    final_status = "succeeded"
    final_error: str | None = None

    with conn() as c:
        run_id = c.execute(
            """
            INSERT INTO ingestion_run (status, source_query, crawler_version)
            VALUES ('running', ?, ?)
            RETURNING id
            """,
            ["open-internet:trending", CRAWLER_VERSION],
        ).fetchone()[0]
        if state:
            state.run_id = run_id
        print(f"[crawl] run_id={run_id}")

        try:
            for ff in _discover_open_internet(c, state, run_id):
                if _stop_requested(state):
                    final_status = "partial"
                    final_error = "ui_stop_requested"
                    _event(c, run_id, "warn", "watchdog_stop:ui_stop_requested")
                    break
                try:
                    total_rules += _process_file(c, ff, run_id, state)
                    total_files += 1
                except Exception as e:
                    msg = f"{type(e).__name__}: {e}"
                    print(f"[crawl] file {ff.project_owner}/{ff.project_name}:{ff.file_path} failed: {msg}", file=sys.stderr)
                    _event(
                        c, run_id, "error",
                        f"file_failed: {ff.project_owner}/{ff.project_name} · {ff.file_path}",
                        {"project": f"{ff.project_owner}/{ff.project_name}",
                         "path": ff.file_path,
                         "error": msg},
                    )

            print(f"\n[crawl] inserted {total_rules} new rules across {total_files} files")
        except Exception as e:
            final_status = "failed"
            final_error = f"{type(e).__name__}: {e}"
            traceback.print_exc()
        finally:
            c.execute(
                """
                UPDATE ingestion_run
                   SET status          = ?,
                       finished_at     = now(),
                       files_fetched   = ?,
                       rules_extracted = ?,
                       rules_new       = ?,
                       error_message   = ?
                 WHERE id = ?
                """,
                [final_status, total_files, total_rules, total_rules, final_error, run_id],
            )
            if state:
                state.status = final_status
                state.error = final_error


# -----------------------------------------------------------------------------
# Continuous mode (local version of ADR-001 §Decision)
# -----------------------------------------------------------------------------

def continuous_loop(state: CrawlState) -> None:
    """Run one discovery pass, sleep PASS_INTERVAL_SECONDS, repeat — until
    stop_event. Re-crawls of the same repo are cheap thanks to rules_file
    UNIQUE constraints + the SKIP_RECENT_HOURS short-circuit, so the loop is
    effectively idempotent. Laptop sleep is handled by the OS suspending the
    whole process; on wake the loop continues from its current iteration."""
    state.status = "running"
    state.error = None
    state.last_message = "continuous mode started"

    # Wire the GitHub adapter's rate-limit pause to our stop event so a
    # multi-minute "wait for cap reset" doesn't make Stop unresponsive.
    set_github_stop_event(state.stop_event)
    try:
        _continuous_loop_inner(state)
    finally:
        set_github_stop_event(None)


def _continuous_loop_inner(state: CrawlState) -> None:
    last_pass_end: float = 0.0
    pass_n = 0
    while not state.stop_event.is_set():
        now = time.time()
        wait_remaining = (last_pass_end + PASS_INTERVAL_SECONDS) - now
        if pass_n == 0 or wait_remaining <= 0:
            pass_n += 1
            state.last_message = f"pass {pass_n} started"
            try:
                run_one_pass(state=state)
            except Exception as e:
                state.error = f"pass {pass_n}: {type(e).__name__}: {e}"
                traceback.print_exc()
            last_pass_end = time.time()
            secs = int(PASS_INTERVAL_SECONDS)
            label = f"{secs} s" if secs < 60 else f"{secs // 60} min"
            state.last_message = f"pass {pass_n} done — next pass in {label}"
        else:
            state.stop_event.wait(timeout=min(POLL_INTERVAL_SECONDS, wait_remaining))

    state.status = "stopped"
    state.last_message = "stopped by user"


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

@click.command()
@click.option("--stats", "do_stats", is_flag=True, help="Print row counts and exit.")
def main(do_stats: bool) -> None:
    if do_stats:
        with conn(read_only=True) as c:
            for tbl in ("source_project", "rules_file", "rule",
                        "rule_llm_decision", "rule_human_label",
                        "ingestion_run", "ingestion_event"):
                count = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                print(f"{tbl:20s} {count:>8d}")
        return

    # Default: run one discovery pass.
    run_one_pass(state=None)


if __name__ == "__main__":
    main()
