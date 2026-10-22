"""Gateway callback: every model call goes into the project's spend ledger, and no call starts once the project's
budget is spent. The ledger and the cap are shared with the rule pipeline: `rule_pipeline/spend.py` in assign+group
(ledger `rules in the wild/spend.jsonl`, cap RITW_BUDGET_USD in ~/Desktop/DAPlab/.env).

    python -m rule_pipeline.spend      (from assign+group) totals by source and by day

A refused call is answered with HTTP 400, which Claude Code does not retry (a 5xx would be retried several times).
A call that used tokens but has no cost means the price is missing (config.yaml): the ledger would under-count, so the
gateway refuses every later call until it is restarted with a price.

Each ledger row also has `run`: the request's `x-ritw-run` header, which each run's agent and judge send
(scripts/run.sh sets RITW_RUN; the task configs pass it to Claude Code as ANTHROPIC_CUSTOM_HEADERS), so cost can be
summed per task, arm and run (scripts/compare_arms.py); and the cache tokens, which the price depends on.
"""
import sys
from pathlib import Path

from fastapi import HTTPException
from litellm.integrations.custom_logger import CustomLogger

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "assign+group"))
from rule_pipeline import spend                            # noqa: E402

SOURCE = "MTAC experiment gateway"


class BudgetGuard(CustomLogger):

    def __init__(self):
        super().__init__()
        self.price_missing = None

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        if self.price_missing:
            raise HTTPException(status_code=400, detail=f"gateway: no price for {self.price_missing}; the spend "
                                "ledger would under-count. Set the prices in scripts/gateway/config.yaml and restart.")
        try:
            spend.check(SOURCE)
        except spend.BudgetExceeded as e:
            raise HTTPException(status_code=400, detail=f"gateway: {e}")
        return data

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        usage = _get(response_obj, "usage")
        tokens_in = _get(usage, "prompt_tokens") or _get(usage, "input_tokens")
        tokens_out = _get(usage, "completion_tokens") or _get(usage, "output_tokens")
        cache_read = _get(usage, "cache_read_input_tokens") or _get(_get(usage, "prompt_tokens_details"), "cached_tokens")
        cache_write = _get(usage, "cache_creation_input_tokens")
        cost = kwargs.get("response_cost") or 0.0
        spend.record(SOURCE, kwargs.get("model"), cost, tokens_in, tokens_out, run=_run(kwargs),
                     cache_read=cache_read, cache_write=cache_write)
        if not cost and (tokens_in or tokens_out):
            self.price_missing = kwargs.get("model") or "this model"
            print(f"gateway: a call with tokens was priced $0 ({self.price_missing}); refusing later calls",
                  file=sys.stderr)


def _get(obj, key):
    """A field of a usage object or dict (LiteLLM returns either)."""
    if obj is None:
        return None
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def _run(kwargs) -> str | None:
    """The request's x-ritw-run header: which task, arm and run made the call."""
    params = kwargs.get("litellm_params") or {}
    for headers in ((params.get("proxy_server_request") or {}).get("headers"), (params.get("metadata") or {}).get("headers")):
        for key, value in (headers or {}).items():
            if key.lower() == "x-ritw-run":
                return value
    return None


guard = BudgetGuard()
