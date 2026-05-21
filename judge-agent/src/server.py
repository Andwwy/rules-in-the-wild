"""FastAPI server + worker thread for the judge dashboard.

Endpoints:
  POST /api/start  → spawn worker if not running
  POST /api/stop   → set stop flag, close httpx client to drop in-flight call
  GET  /api/state  → snapshot for the UI (status, current rule, recent
                      results, spend, cap, total processed)
  GET  /            → static dashboard (single HTML page, vanilla JS)

The worker runs in a daemon thread. The DuckDB connection is owned by the
worker thread (DuckDB connections are not thread-safe; the API handlers
read state from a shared dict guarded by a lock, NOT from the connection).

"Stop during inference" semantics:
  - Stop sets `_stop_event` AND calls `judge.cancel()` (closes the HTTPX
    client). Any in-flight `_client.post(...)` raises a transport error
    immediately; tenacity will retry once or twice then give up. The
    worker catches, sees `_stop_event` is set, and exits without writing
    a row for the partial. That row stays unjudged and gets picked up on
    the next start.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.cost import Budget, BudgetExceeded
from src.db import connect
from src.judge import Judge, JudgeResult, TAXONOMY_AXES
from src.work_queue import next_batch, record_decision


log = logging.getLogger("judge.server")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


# ----- shared state, protected by _state_lock -----
_state_lock = threading.Lock()
_state: dict[str, Any] = {
    "status": "idle",  # idle | running | stopping
    "started_at": None,
    "stopped_at": None,
    "current_rule": None,  # see _set_current() for shape
    "recent": deque(maxlen=20),  # newest first
    "spent_usd": 0.0,
    "max_usd": 0.0,
    # total_judged: rows that wrote to rule_llm_decision with parse_ok=true
    # total_parse_failed: rows written with parse_ok=false (axis mix-up, JSON,
    #   missing key, etc.) — still recorded, just not usable as a label
    # total_failed: infra failures (network/DB exceptions) — no row written
    "total_judged": 0,
    "total_parse_failed": 0,
    "total_failed": 0,
    "prompt_version": None,
    "model": None,
    "error": None,
}
_stop_event = threading.Event()
_worker_thread: threading.Thread | None = None
_active_judge: Judge | None = None  # so /api/stop can call judge.cancel()
_active_budget: Budget | None = None  # so /api/cap can mutate at runtime


def _state_snapshot() -> dict[str, Any]:
    with _state_lock:
        return {
            **_state,
            "recent": list(_state["recent"]),
        }


def _set(key: str, value: Any) -> None:
    with _state_lock:
        _state[key] = value


def _set_many(**kwargs: Any) -> None:
    with _state_lock:
        _state.update(kwargs)


def _push_recent(entry: dict[str, Any]) -> None:
    with _state_lock:
        _state["recent"].appendleft(entry)


def _fetch_document_text(con, rule_id: str) -> tuple[str, str, int, int]:
    """Return (source_path, document_text, start_line, end_line) for a rule."""
    row = con.execute(
        """
        SELECT f.path, f.raw_content, r.line_start, r.line_end
        FROM rule r
        JOIN rules_file f ON f.id = r.rules_file_id
        WHERE r.id::VARCHAR = ?
        """,
        [rule_id],
    ).fetchone()
    if not row:
        return ("", "", 0, 0)
    return (row[0], row[1], int(row[2]), int(row[3]))


def _build_current_payload(
    rule_id: str, rule_text: str, source_kind: str, con
) -> dict[str, Any]:
    path, doc_text, start_line, end_line = _fetch_document_text(con, rule_id)
    lines = doc_text.replace("\r", "").split("\n") if doc_text else []
    context = 8
    lower = max(1, start_line - context)
    upper = min(len(lines), end_line + context)
    source_lines = [
        {"line_number": i, "text": lines[i - 1], "highlighted": start_line <= i <= end_line}
        for i in range(lower, upper + 1)
    ] if lines else []
    return {
        "rule_id": rule_id,
        "rule_text": rule_text,
        "source_kind": source_kind,
        "source_path": path,
        "start_line": start_line,
        "end_line": end_line,
        "source_lines": source_lines,
        "started_at": time.time(),
    }


def _result_payload(
    rule_id: str, rule_text: str, source_path: str, result: JudgeResult
) -> dict[str, Any]:
    label = result.label
    return {
        "rule_id": rule_id,
        "rule_text": rule_text,
        "source_path": source_path,
        "parse_ok": result.parse_ok,
        "parse_error": result.parse_error,
        "values": (label.values if label else {}),
        "artifacts_required": (label.artifacts_required if label else []),
        "confidence": (label.confidence if label else None),
        "rationale": (label.rationale if label else None),
        "latency_ms": result.latency_ms,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cost_usd": Budget.cost(result.input_tokens, result.output_tokens),
        "at": time.time(),
    }


def _worker() -> None:
    """Worker thread. Owns its own DuckDB connection + Judge instance."""
    global _active_judge, _active_budget
    try:
        con = connect()
        judge = Judge(con)
        budget = Budget(con)
        _active_judge = judge
        _active_budget = budget
        _set_many(
            prompt_version=judge.prompt_version,
            model=__import__("src.judge", fromlist=["JUDGE_MODEL"]).JUDGE_MODEL,
            max_usd=budget.max_usd,
            spent_usd=budget.spent_usd,
            status="running",
            started_at=time.time(),
            stopped_at=None,
            error=None,
        )
        log.info(
            "worker started: model=%s prompt_version=%s cap=$%.4f spent=$%.4f",
            __import__("src.judge", fromlist=["JUDGE_MODEL"]).JUDGE_MODEL,
            judge.prompt_version,
            budget.max_usd,
            budget.spent_usd,
        )
        while not _stop_event.is_set():
            batch = next_batch(con, limit=20)
            if not batch:
                log.info("queue empty; sleeping 30s")
                # Sleep in 1s slices so /api/stop is responsive.
                for _ in range(30):
                    if _stop_event.is_set():
                        break
                    time.sleep(1)
                continue
            for rule_id, rule_text, source_kind in batch:
                if _stop_event.is_set():
                    break
                if budget.would_exceed():
                    log.warning(
                        "cap reached: spent=$%.4f cap=$%.4f", budget.spent_usd, budget.max_usd
                    )
                    _set("error", f"budget cap reached (${budget.max_usd:.4f})")
                    _stop_event.set()
                    break
                _set("current_rule", _build_current_payload(rule_id, rule_text, source_kind, con))
                try:
                    result = judge.classify(rule_text, source_kind)
                except Exception as e:
                    # Includes the "stopped mid-inference" path: judge.cancel()
                    # closed the client, the in-flight post raised.
                    if _stop_event.is_set():
                        log.info("dropped rule %s mid-inference (stop requested)", rule_id)
                    else:
                        log.exception("judge call failed for rule %s: %s", rule_id, e)
                        with _state_lock:
                            _state["total_failed"] += 1
                    continue
                try:
                    record_decision(con, rule_id, result, judge.prompt_version)
                    budget.add(result.input_tokens, result.output_tokens)
                except BudgetExceeded as e:
                    log.warning("budget exceeded after rule %s: %s", rule_id, e)
                    _set("error", str(e))
                    _stop_event.set()
                    break
                except Exception as e:
                    log.exception("record_decision failed for rule %s: %s", rule_id, e)
                    with _state_lock:
                        _state["total_failed"] += 1
                    continue
                # Update visible state
                with _state_lock:
                    _state["spent_usd"] = budget.spent_usd
                    if result.parse_ok:
                        _state["total_judged"] += 1
                    else:
                        _state["total_parse_failed"] += 1
                src_path = (
                    _state["current_rule"]["source_path"]
                    if _state["current_rule"]
                    else ""
                )
                _push_recent(_result_payload(rule_id, rule_text, src_path, result))
                _set("current_rule", None)
    except Exception as e:
        log.exception("worker crashed: %s", e)
        _set("error", f"worker crash: {e}")
    finally:
        _set_many(
            status="idle",
            stopped_at=time.time(),
            current_rule=None,
        )
        _active_judge = None
        _active_budget = None
        log.info("worker stopped")


# ----- FastAPI -----

@asynccontextmanager
async def _lifespan(app: FastAPI):
    # On startup: load persisted cap + spend so the UI can render them even
    # before the worker has been started.
    try:
        con = connect()
        budget_view = Budget(con)
        _set_many(max_usd=budget_view.max_usd, spent_usd=budget_view.spent_usd)
        con.close()
    except Exception as e:
        log.warning("startup load of cap/spend failed: %s", e)
    yield
    # On shutdown, signal worker to stop and join.
    if _worker_thread and _worker_thread.is_alive():
        _stop_event.set()
        if _active_judge:
            _active_judge.cancel()
        _worker_thread.join(timeout=5)


app = FastAPI(title="Judge Agent", lifespan=_lifespan)


@app.get("/api/state")
def get_state() -> dict[str, Any]:
    return _state_snapshot()


@app.post("/api/start")
def start() -> dict[str, Any]:
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return {"status": "already_running"}
    _stop_event.clear()
    _set_many(error=None, status="running")
    _worker_thread = threading.Thread(target=_worker, daemon=True, name="judge-worker")
    _worker_thread.start()
    return {"status": "started"}


@app.post("/api/stop")
def stop() -> dict[str, Any]:
    if not (_worker_thread and _worker_thread.is_alive()):
        return {"status": "not_running"}
    _set("status", "stopping")
    _stop_event.set()
    # Drop any in-flight HTTP call by closing the httpx client from this thread.
    if _active_judge is not None:
        _active_judge.cancel()
    return {"status": "stopping"}


class CapPayload(BaseModel):
    max_usd: float = Field(..., ge=0.0, le=1000.0)


@app.post("/api/cap")
def set_cap(payload: CapPayload) -> dict[str, Any]:
    """Set the spending cap. Works whether the worker is running or not —
    if it's running, the change applies on the next rule; if not, the new
    value persists to `crawl_settings` so the next worker picks it up."""
    if _active_budget is not None:
        _active_budget.set_cap(payload.max_usd)
        _set("max_usd", _active_budget.max_usd)
    else:
        con = connect()
        try:
            Budget(con).set_cap(payload.max_usd)
        finally:
            con.close()
        _set("max_usd", payload.max_usd)
    return {"status": "ok", "max_usd": payload.max_usd}


@app.post("/api/reset-spend")
def reset_spend() -> dict[str, Any]:
    """Clear the persistent spend meter. Useful when raising the cap for a
    new judging session and you want the bar to start at zero."""
    if _active_budget is not None:
        _active_budget.reset_spend()
        _set("spent_usd", 0.0)
    else:
        con = connect()
        try:
            Budget(con).reset_spend()
        finally:
            con.close()
        _set("spent_usd", 0.0)
    return {"status": "ok"}


STATIC_DIR = Path(__file__).resolve().parent / "static"

# Mount static dir if any extra assets land there later; the main dashboard
# is served from /.
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
