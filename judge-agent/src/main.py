"""Entry point for the judge agent.

  python -m src.main --once --limit 20       # batch and exit
  python -m src.main --watch --interval 30   # persistent loop (default)

The polling loop is robust:
  - empty queue → sleep `interval` seconds, retry
  - per-rule exceptions are logged and the rule is skipped (the loop moves on)
  - hitting the budget cap returns from the current pass; next pass will short-
    circuit immediately and keep emitting the cap warning so it stays visible
    in `docker logs`
"""

import argparse
import logging
import time

from src.cost import Budget, BudgetExceeded
from src.db import connect
from src.judge import Judge
from src.work_queue import next_batch, record_decision


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("judge")


def run_pass(con, judge: Judge, budget: Budget, limit: int) -> int:
    batch = next_batch(con, limit=limit)
    if not batch:
        return 0
    processed = 0
    for rule_id, rule_text, source_kind in batch:
        if budget.would_exceed():
            log.warning(
                "budget cap reached: spent=$%.4f cap=$%.4f — stopping pass",
                budget.spent_usd,
                budget.max_usd,
            )
            return processed
        try:
            result = judge.classify(rule_text, source_kind)
        except Exception as e:
            log.exception("judge call failed for rule %s: %s", rule_id, e)
            continue
        try:
            record_decision(con, rule_id, result, judge.prompt_version)
            budget.add(result.input_tokens, result.output_tokens)
        except BudgetExceeded as e:
            log.warning("budget exceeded after rule %s: %s", rule_id, e)
            return processed + 1
        except Exception as e:
            log.exception("record_decision failed for rule %s: %s", rule_id, e)
            continue
        processed += 1
        log.info(
            "judged rule=%s parse_ok=%s confidence=%s latency=%dms spent=$%.4f",
            rule_id,
            result.parse_ok,
            f"{result.label.confidence:.2f}" if result.label else "-",
            result.latency_ms,
            budget.spent_usd,
        )
    return processed


def main() -> None:
    parser = argparse.ArgumentParser(description="Judge agent — classifies rules.")
    parser.add_argument("--once", action="store_true", help="Run one batch and exit.")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Persistent polling loop (default when --once is not set).",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Seconds to sleep between empty passes (default 30).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Rules per pass (default 20).",
    )
    args = parser.parse_args()

    con = connect()
    judge = Judge(con)
    budget = Budget(con)

    from src.judge import JUDGE_MODEL
    log.info("model=%s prompt_version=%s", JUDGE_MODEL, judge.prompt_version)
    log.info(
        "budget cap=$%.4f already_spent=$%.4f",
        budget.max_usd,
        budget.spent_usd,
    )

    if args.once:
        n = run_pass(con, judge, budget, args.limit)
        log.info("done — processed %d rules in this pass", n)
        return

    while True:
        n = run_pass(con, judge, budget, args.limit)
        if n == 0:
            log.info("no unjudged rules; sleeping %ds", args.interval)
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
