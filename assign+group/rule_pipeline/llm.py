"""The only module that talks to a model.

Two functions do all the work of the pipeline:

    call(prompt, user_input, schema, settings)     one request, answer constrained to a JSON schema
    run_many(items, ...)                           `call` over many items: threaded, batched, checkpointed, resumable

The provider is one switch, `Settings.provider`: `perplexity` (alias `pplx`, the default), `openai` or `bedrock`. ROUTES
says how each one is reached; nothing outside this module knows. Perplexity's Agent API is called directly (LiteLLM's
Perplexity route posts to the old /v1/responses and cannot send `response_format`); OpenAI and Bedrock go through LiteLLM.
A model is named once, vendor-first (`openai/gpt-5.6-terra`), and each route spells it its own way.

    python -m rule_pipeline.llm --check perplexity openai bedrock      one tiny request per provider, to test the keys
"""
from __future__ import annotations

import copy
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

import requests

from . import spend


# ── settings ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Settings:
    """Defaults are the lab's current settings."""
    provider: str = "perplexity"
    model: str = "openai/gpt-5.6-terra"   # vendor/model; each route spells it its own way
    tier: str | None = None               # None = the route's own default (flex where the provider has it)
    effort: str = "high"
    workers: int = 20          # concurrent requests
    batch_size: int = 1        # items per request

    def but(self, **changes) -> "Settings":
        return replace(self, **{k: v for k, v in changes.items() if v is not None})


class LLMError(RuntimeError):
    """One request failed after its retries; the item is recorded with the error and retried on the next run."""


class FatalLLMError(LLMError):
    """Retrying cannot help (bad key, no quota, unknown provider, a setting the provider rejects) — the whole run stops."""


class _RateLimited(Exception):
    def __init__(self, message: str, wait: float | None):
        super().__init__(message)
        self.wait = wait


# ── routes ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Route:
    keys: tuple[str, ...]                  # env variables, any one of which authenticates; () = AWS credential chain
    model: Callable[[str], str]            # vendor/model -> the name this route sends
    tier: str | None                       # default service tier; None = send none
    send: Callable[["Route", Settings, str, str, dict], tuple[str, dict]]   # -> (answer text, usage)


def _vendor_model(model: str) -> tuple[str, str]:
    vendor, _, name = model.partition("/")
    return (vendor, name) if name else ("", vendor)


def _openai_model(model: str) -> str:
    vendor, name = _vendor_model(model)
    if vendor not in ("", "openai"):
        raise FatalLLMError(f"the openai provider only serves OpenAI models, not {model!r}")
    return f"openai/{name}"


def _bedrock_model(model: str) -> str:
    """Bedrock spells a model `vendor.name`. OpenAI models go to Bedrock's OpenAI-compatible (Mantle) endpoint, which
    keeps strict JSON schemas; other vendors go through the Converse API."""
    vendor, name = _vendor_model(model)
    if not vendor:
        return f"bedrock/converse/{name}"                  # already a Bedrock model id
    return f"bedrock_mantle/{vendor}.{name}" if vendor == "openai" else f"bedrock/converse/{vendor}.{name}"


def strict_schema(schema):
    """The same schema in the form strict mode accepts (every object closed, every property required), or None.

    Strict mode makes the reply follow the schema; without it a vote reply once came back with an axis as plain strings
    instead of {value, attempts} objects and crashed the vote. The pipeline's schemas already require every property;
    the assignment schema only lacks `additionalProperties: false`, which this adds."""
    if isinstance(schema, list):
        out = [strict_schema(s) for s in schema]
        return None if any(s is None for s in out) else out
    if not isinstance(schema, dict):
        return schema
    out = {}
    for k, v in schema.items():
        if isinstance(v, (dict, list)):
            v = strict_schema(v) if k != "properties" else {p: strict_schema(sub) for p, sub in v.items()}
            if v is None or (isinstance(v, dict) and any(x is None for x in v.values())):
                return None
        out[k] = v
    if out.get("type") == "object" and "properties" in out:
        if set(out.get("required", [])) != set(out["properties"]):
            return None                                   # an optional property: strict mode cannot express it
        out["additionalProperties"] = False
    return out


def _json_format(schema: dict) -> dict:
    strict = strict_schema(schema)
    return {"name": "answer", "schema": strict or schema, "strict": strict is not None}


PERPLEXITY_URL = "https://api.perplexity.ai/v1/agent"


def _send_perplexity(route: Route, s: Settings, prompt: str, user_input: str, schema: dict) -> tuple[str, dict]:
    """Perplexity's Agent API, directly."""
    body = {
        "model": route.model(s.model),
        "instructions": prompt,
        "input": [{"type": "message", "role": "user", "content": user_input}],
        "reasoning": {"effort": s.effort},
        "response_format": {"type": "json_schema", "json_schema": _json_format(schema)},
    }
    if tier := s.tier or route.tier:
        body["service_tier"] = tier
    key = os.environ[route.keys[0]]
    response = requests.post(PERPLEXITY_URL, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                             json=body, timeout=900)
    if response.status_code in (401, 403):               # rejected key or exhausted quota
        raise FatalLLMError(f"perplexity refused the request ({response.status_code}): {response.text[:300]}")
    if response.status_code == 429:
        _rate_limited(response.text, response.headers.get("retry-after"))
    response.raise_for_status()
    raw = response.json()
    text = "".join(part.get("text", "")
                   for item in raw.get("output", []) if item.get("type") == "message"
                   for part in item.get("content", []) if part.get("type") == "output_text")
    usage = raw.get("usage", {})
    return text, {"input": usage.get("input_tokens"), "output": usage.get("output_tokens"),
                  "cost": (usage.get("cost") or {}).get("total_cost")}


def _send_litellm(route: Route, s: Settings, prompt: str, user_input: str, schema: dict) -> tuple[str, dict]:
    """OpenAI and Bedrock through LiteLLM. drop_params stays off: a setting the route cannot take stops the run instead
    of being dropped silently (LiteLLM's plain `bedrock/openai.*` route, for one, sends neither schema nor effort)."""
    import litellm                                         # imported here: slow to import, and only these routes need it

    kwargs = {
        "model": route.model(s.model),
        "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": user_input}],
        "response_format": {"type": "json_schema", "json_schema": _json_format(schema)},
        "reasoning_effort": s.effort,
        "timeout": 900,
        "num_retries": 0,                                  # retries are call()'s job
        "drop_params": False,
    }
    if tier := s.tier or route.tier:
        kwargs["service_tier"] = tier
    if region := os.environ.get("AWS_REGION_NAME") or os.environ.get("AWS_REGION"):
        if kwargs["model"].startswith("bedrock"):
            kwargs["aws_region_name"] = region
    try:
        response = litellm.completion(**kwargs)
    except (litellm.AuthenticationError, litellm.PermissionDeniedError, litellm.UnsupportedParamsError,
            litellm.NotFoundError) as e:
        raise FatalLLMError(f"{s.provider} refused the request: {str(e)[:300]}") from e
    except litellm.RateLimitError as e:
        headers = getattr(getattr(e, "response", None), "headers", None) or {}
        _rate_limited(str(e), headers.get("retry-after"))
    text = response.choices[0].message.content or ""
    usage = response.usage
    details = getattr(usage, "completion_tokens_details", None)
    try:
        cost = litellm.completion_cost(completion_response=response)
    except Exception:                                      # a model missing from LiteLLM's price list
        cost = None
    return text, {"input": usage.prompt_tokens, "output": usage.completion_tokens,
                  "reasoning": getattr(details, "reasoning_tokens", None), "cost": cost}


def _rate_limited(message: str, retry_after) -> None:
    if "insufficient_quota" in message:                   # out of credit: waiting will not help
        raise FatalLLMError(f"no quota left: {message[:300]}")
    try:
        wait = float(retry_after) if retry_after else None
    except ValueError:
        wait = None
    raise _RateLimited(message[:300], wait)


ROUTES = {
    "perplexity": Route(("PERPLEXITY_API_KEY",), lambda m: m, "flex", _send_perplexity),
    "openai": Route(("OPENAI_API_KEY",), _openai_model, "flex", _send_litellm),
    # Bedrock: a Bedrock API key, else the standard AWS credential chain (env, ~/.aws, role). Mantle takes no flex tier.
    "bedrock": Route((), _bedrock_model, None, _send_litellm),
}
ALIASES = {"pplx": "perplexity", "aws": "bedrock"}


def route_of(settings: Settings) -> Route:
    name = ALIASES.get(settings.provider, settings.provider)
    if name not in ROUTES:
        raise FatalLLMError(f"unknown provider {settings.provider!r}; available: {sorted(ROUTES)} (aliases {ALIASES})")
    route = ROUTES[name]
    if route.keys and not any(os.environ.get(k) for k in route.keys):
        raise FatalLLMError(f"{' or '.join(route.keys)} is not set — put it in DAPlab/.env, a .env next to the run, "
                            f"or export it")
    return route


# ── one request ──────────────────────────────────────────────────────────────────────────────────────────────────────────
RATE_LIMIT_ATTEMPTS = 6


def call(prompt: str, user_input: str, schema: dict, settings: Settings, attempts: int = 3) -> tuple[dict, dict]:
    """One request. Returns (parsed JSON answer, usage). Retries with backoff, then raises LLMError.

    A 429 gets its own, longer budget: it waits as long as the provider's Retry-After says (else 10, 20, 40 … s).
    Every answered request goes into the project's spend ledger, and none starts once its budget is spent (spend.py)."""
    route = route_of(settings)
    error, failures, limited = None, 0, 0
    while failures < attempts and limited < RATE_LIMIT_ATTEMPTS:
        try:
            spend.check(f"rule pipeline / {settings.provider}")
        except spend.BudgetExceeded as e:
            raise FatalLLMError(str(e)) from e
        try:
            text, usage = route.send(route, settings, prompt, user_input, schema)
            spend.record(f"rule pipeline / {settings.provider}", route.model(settings.model), usage.get("cost"),
                         usage.get("input"), usage.get("output"))
            return json.loads(text), usage
        except FatalLLMError:
            raise
        except _RateLimited as e:
            limited += 1
            error = f"rate limited: {e}"
            time.sleep(min(e.wait if e.wait is not None else 10 * 2 ** (limited - 1), 300))
        except Exception as e:                       # network, HTTP status, or an answer that is not JSON
            failures += 1
            error = f"{type(e).__name__}: {e}"
            time.sleep(2 * failures)
    raise LLMError(error)


# ── many requests ────────────────────────────────────────────────────────────────────────────────────────────────────────
BATCH_NOTE = ("Several items are given above, each under a header line that names its {key}. Answer every item "
              "independently of the others, exactly as you would if it were the only one. Return one result per item in "
              "`results`, each carrying the {key} from the item's header.")


def _batch_schema(schema: dict, key: str) -> dict:
    item = copy.deepcopy(schema)
    item.setdefault("properties", {})[key] = {"type": "string"}
    item["required"] = [key, *item.get("required", [])]
    return {"type": "object", "properties": {"results": {"type": "array", "items": item}}, "required": ["results"]}


def read_checkpoint(path: Path, key: str) -> dict:
    """Finished records by key. Records carrying an `error` are left out, so a rerun retries them."""
    done = {}
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:             # a torn last line from a hard kill
                continue
            if not record.get("error"):
                done[record[key]] = record
    return done


def run_many(items: list[dict], *, key: str, make_input: Callable[[dict], str], to_record: Callable, prompt: str,
             schema: dict, settings: Settings, checkpoint: Path, label: str = "") -> dict:
    """`call` for every item → {item[key]: record}.

    make_input(item) -> the user message for one item
    to_record(item, answer, usage, error) -> the dict to keep (must contain `key`); answer is None when error is set
    `settings.workers` requests run at once, `settings.batch_size` items go into each request. Every finished record is
    appended to `checkpoint`; running again skips what is there and retries what failed.
    """
    done = read_checkpoint(checkpoint, key)
    todo = [item for item in items if item[key] not in done]
    print(f"{label}: {len(items)} items | {len(done)} already done | {len(todo)} to run | "
          f"{settings.workers} workers × batch {settings.batch_size} | {settings.model} / {settings.effort}", flush=True)
    if not todo:
        return done

    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    lock, started, finished, fatal = threading.Lock(), time.time(), [0], []

    def keep(item, answer, usage, error, out):
        record = to_record(item, answer, usage, error)
        with lock:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            done[item[key]] = record
            finished[0] += 1
            if finished[0] % 100 == 0:
                print(f"  {label}: {finished[0]}/{len(todo)}  {(time.time() - started) / 60:.1f} min", flush=True)

    def one(item, out):
        if fatal:                                    # another thread already hit a fatal error: do not keep knocking
            return
        try:
            answer, usage = call(prompt, make_input(item), schema, settings)
            keep(item, answer, usage, None, out)
        except FatalLLMError as e:
            fatal.append(str(e))
        except LLMError as e:
            keep(item, None, None, str(e), out)

    def batch(group, out):
        """Several items in one request. Any item the reply drops, repeats or invents is redone on its own."""
        user_input = "\n\n".join(f"### {key} = {item[key]}\n{make_input(item)}" for item in group)
        user_input += "\n\n" + BATCH_NOTE.format(key=key)
        if fatal:
            return
        try:
            answer, usage = call(prompt, user_input, _batch_schema(schema, key), settings)
            results = answer.get("results", [])
        except FatalLLMError as e:
            fatal.append(str(e))
            return
        except LLMError:
            results, usage = [], None
        ids = [r.get(key) for r in results]
        share = {k: (v / len(group) if isinstance(v, (int, float)) else v) for k, v in (usage or {}).items()}
        for item in group:
            if ids.count(item[key]) == 1:
                result = dict(next(r for r in results if r.get(key) == item[key]))
                result.pop(key)
                keep(item, result, share | {"batched": len(group)}, None, out)
            else:
                one(item, out)

    size = max(1, settings.batch_size)
    groups = [todo[i:i + size] for i in range(0, len(todo), size)]
    with checkpoint.open("a") as out, ThreadPoolExecutor(max_workers=max(1, settings.workers)) as pool:
        list(pool.map(lambda g: one(g[0], out) if len(g) == 1 else batch(g, out), groups))
    if fatal:
        raise SystemExit(f"{label}: stopped — {fatal[0]}")
    failed = sum(1 for record in done.values() if record.get("error"))
    if failed:
        print(f"  {label}: {failed} items failed and will be retried on the next run", flush=True)
    return done


# ── key check ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def load_env(*starts: Path) -> None:
    """Every `.env` from each start folder up to the root, nearest first; a variable already set is never overwritten,
    so the nearest file wins and a lab-wide DAPlab/.env fills in the rest."""
    from dotenv import load_dotenv
    seen = set()
    for start in starts:
        for folder in (start.resolve(), *start.resolve().parents):
            if folder not in seen and (folder / ".env").is_file():
                load_dotenv(folder / ".env", override=False)
            seen.add(folder)


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="rule_pipeline.llm", description="Send one tiny request per provider to test the keys.")
    p.add_argument("--check", nargs="+", required=True, metavar="PROVIDER", help=f"any of {sorted(ROUTES)}")
    p.add_argument("--model", default=Settings.model)
    p.add_argument("--effort", default="low")
    args = p.parse_args(argv)
    load_env(Path.cwd(), Path(__file__).parent)
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
    failed = 0
    for provider in args.check:
        settings = Settings(provider=provider, model=args.model, effort=args.effort)
        try:
            answer, usage = call('Reply with {"ok": true}.', "ping", schema, settings, attempts=1)
            print(f"{provider:<11} ok    {answer}  {usage}")
        except LLMError as e:
            failed += 1
            print(f"{provider:<11} FAIL  {str(e)[:300]}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
