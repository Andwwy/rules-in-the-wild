"""One spend ledger and one budget for every model call in "rules in the wild".

    python -m rule_pipeline.spend          totals by source and by day, the cap, what is left

Every caller records each finished call here and checks the cap before the next one: the rule pipeline (`llm.call`)
and the MTAC experiment's gateway (`experiment/scripts/gateway/budget.py`). Standard library only, so any environment can
import it.

    ledger   RITW_SPEND_LEDGER, default `rules in the wild/spend.jsonl` (kept local; not published)
    cap      RITW_BUDGET_USD in USD, default 50; set it in ~/Desktop/DAPlab/.env

A call that starts under the cap can end over it by its own cost. Calls whose provider reports no price are logged
with their tokens and count as $0.
"""
from __future__ import annotations

import collections
import fcntl
import json
import os
import time
from pathlib import Path

DEFAULT_LEDGER = Path(__file__).resolve().parents[2] / "spend.jsonl"
DEFAULT_CAP = 50.0


class BudgetExceeded(RuntimeError):
    """The project's budget is spent; no further model call may start."""


def ledger() -> Path:
    return Path(os.environ.get("RITW_SPEND_LEDGER") or DEFAULT_LEDGER)


def cap() -> float:
    return float(os.environ.get("RITW_BUDGET_USD") or DEFAULT_CAP)


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:                      # a torn last line from a hard kill
            continue
    return rows


def spent() -> float:
    return sum(r.get("cost") or 0.0 for r in _rows(ledger()))


def check(source: str = "") -> None:
    """Raise BudgetExceeded once the ledger has reached the cap."""
    total, limit = spent(), cap()
    if total >= limit:
        raise BudgetExceeded(f"rules-in-the-wild budget spent: ${total:.2f} of ${limit:.2f}"
                             f"{f' ({source})' if source else ''}; raise RITW_BUDGET_USD to continue")


def record(source: str, model: str | None, cost: float | None, input_tokens=None, output_tokens=None, **extra) -> None:
    """Append one finished call. Safe across threads and processes (an exclusive lock around the append)."""
    path = ledger()
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "source": source, "model": model,
           "input": input_tokens, "output": output_tokens, "cost": cost, **extra}
    with path.open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def main():
    rows = _rows(ledger())
    by_source, by_day = collections.defaultdict(float), collections.defaultdict(float)
    for r in rows:
        by_source[r.get("source") or "?"] += r.get("cost") or 0.0
        by_day[(r.get("time") or "?")[:10]] += r.get("cost") or 0.0
    total, limit = sum(by_source.values()), cap()
    print(f"ledger {ledger()}  ({len(rows)} calls)")
    for name, part in (("source", by_source), ("day", by_day)):
        for k, v in sorted(part.items()):
            print(f"  {name:<6} {k:<40} ${v:9.4f}")
    print(f"total ${total:.4f} of ${limit:.2f}, ${max(0.0, limit - total):.4f} left")


if __name__ == "__main__":
    main()
