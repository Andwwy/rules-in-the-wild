"""The only module that talks to a model.

Two functions do all the work of the pipeline:

    call(prompt, user_input, schema, settings)     one request, answer constrained to a JSON schema
    run_many(items, ...)                           `call` over many items: threaded, batched, checkpointed, resumable

A provider is a URL, the name of the key variable, and two small functions (build the request body, read the reply).
Perplexity is the default and the only one written; adding another means adding one entry to PROVIDERS.
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


# ── settings ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Settings:
    """Defaults are the lab's current settings."""
    provider: str = "perplexity"
    model: str = "openai/gpt-5.6-terra"
    tier: str = "flex"
    effort: str = "high"
    workers: int = 20          # concurrent requests
    batch_size: int = 1        # items per request

    def but(self, **changes) -> "Settings":
        return replace(self, **{k: v for k, v in changes.items() if v is not None})


# ── providers ────────────────────────────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Provider:
    url: str
    key_env: str
    build_body: Callable[[Settings, str, str, dict], dict]
    parse: Callable[[dict], tuple[str, dict]]          # raw reply -> (answer text, usage)


def _perplexity_body(s: Settings, prompt: str, user_input: str, schema: dict) -> dict:
    return {
        "model": s.model,
        "instructions": prompt,
        "input": [{"type": "message", "role": "user", "content": user_input}],
        "reasoning": {"effort": s.effort},
        "service_tier": s.tier,
        "response_format": {"type": "json_schema", "json_schema": {"schema": schema}},
    }


def _perplexity_parse(raw: dict) -> tuple[str, dict]:
    text = "".join(part.get("text", "")
                   for item in raw.get("output", []) if item.get("type") == "message"
                   for part in item.get("content", []) if part.get("type") == "output_text")
    usage = raw.get("usage", {})
    return text, {"input": usage.get("input_tokens"), "output": usage.get("output_tokens"),
                  "cost": (usage.get("cost") or {}).get("total_cost")}


PROVIDERS = {
    "perplexity": Provider("https://api.perplexity.ai/v1/agent", "PERPLEXITY_API_KEY", _perplexity_body, _perplexity_parse),
}


class LLMError(RuntimeError):
    """One request failed after its retries; the item is recorded with the error and retried on the next run."""


class FatalLLMError(LLMError):
    """Retrying cannot help (bad key, no quota, unknown provider) — the whole run stops."""


def _provider(settings: Settings) -> tuple[Provider, str]:
    if settings.provider not in PROVIDERS:
        raise FatalLLMError(f"unknown provider {settings.provider!r}; available: {sorted(PROVIDERS)}")
    provider = PROVIDERS[settings.provider]
    key = os.environ.get(provider.key_env)
    if not key:
        raise FatalLLMError(f"{provider.key_env} is not set — put it in .env or export it")
    return provider, key


# ── one request ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def call(prompt: str, user_input: str, schema: dict, settings: Settings, attempts: int = 3) -> tuple[dict, dict]:
    """One request. Returns (parsed JSON answer, usage). Retries with backoff, then raises LLMError."""
    provider, key = _provider(settings)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = provider.build_body(settings, prompt, user_input, schema)
    error = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(provider.url, headers=headers, json=body, timeout=900)
            if response.status_code in (401, 403):   # rejected key or exhausted quota
                raise FatalLLMError(f"{settings.provider} refused the request ({response.status_code}): {response.text[:300]}")
            response.raise_for_status()
            text, usage = provider.parse(response.json())
            return json.loads(text), usage
        except FatalLLMError:
            raise
        except Exception as e:                       # network, HTTP status, or an answer that is not JSON
            error = f"{type(e).__name__}: {e}"
            time.sleep(2 * attempt)
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
