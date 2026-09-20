"""Judge 30k sampled clauses with the judge_test.ipynb prompt, verbatim.

Same MODEL / EFFORT / SERVICE_TIER / N_EXAMPLES / rubric as the notebook; batch=5,
30 rps ceiling, 30 workers.  Only rule_clause + context go into the call; only
is_rule comes back.  `rule ID` (text_sha) rides along for provenance and is never
shown to the model -- the per-call integer ID is a local row index.

Resumable: every completed chunk is appended to a jsonl checkpoint, so a crash or
kill loses at most the calls in flight.
"""
import json, os, re, time, threading, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
for ln in open(".env"):
    if "=" in ln and not ln.startswith("#"):
        k, v = ln.strip().split("=", 1); os.environ.setdefault(k, v.strip('"\''))
KEY = os.environ["PERPLEXITY_API_KEY"]

MODEL, EFFORT, TIER, N_EXAMPLES = "openai/gpt-5.6-terra", "minimal", "flex", 50
BATCH, RPS, WORKERS = 5, 30, 30
API = "https://api.perplexity.ai/v1/agent"
CKPT, OUT = "/tmp/30k_ckpt.jsonl", "data/30k filter result.json"

rows = json.load(open("/tmp/30k_input.json"))
examples = json.load(open("data/50 sample in prompt.json"))[:N_EXAMPLES]

render = lambda e: f'ID: {e["ID"]}\nRULE: {e["rule"]}\nCONTEXT:\n{e["context"]}'
render_row = lambda r: f'ID: {r["i"]}\nRULE: {r["rule_clause"]}\nCONTEXT:\n{r["context"]}'

src = "".join("".join(c["source"]) for c in json.load(open("judge_test.ipynb"))["cells"]
              if c["cell_type"] == "code")
RUBRIC = re.search(r'RUBRIC = """(.*?)"""', src, re.S).group(1)
SYSTEM = (RUBRIC.strip() + "\n\n## Examples\n\n" +
          "\n\n".join(render(e) + f'\n→ is_rule: {str(e["is_rule"]).lower()}'
                      + (f'  ({e["reason"]})' if e["reason"] else "") for e in examples))

done = {}
if os.path.exists(CKPT):
    for ln in open(CKPT):
        d = json.loads(ln); done[d["i"]] = d["is_rule"]
    print(f"resuming: {len(done):,} rows already judged")

todo = [r for r in rows if r["i"] not in done]
chunks = [todo[i:i+BATCH] for i in range(0, len(todo), BATCH)]
print(f"{len(rows):,} rows | {len(todo):,} to judge | {len(chunks):,} calls "
      f"| batch={BATCH} rps={RPS} workers={WORKERS} effort={EFFORT}")

_lock, _slots, _wlock = threading.Lock(), [], threading.Lock()
_ck = open(CKPT, "a")
def throttle():
    while True:
        with _lock:
            now = time.time()
            _slots[:] = [t for t in _slots if now - t < 1.0]
            if len(_slots) < RPS:
                _slots.append(now); return
            wait = 1.0 - (now - _slots[0])
        time.sleep(max(wait, 0.005))

def one(ch):
    body = {"model": MODEL, "instructions": SYSTEM,
            "input": "\n\n".join(render_row(r) for r in ch),
            "reasoning": {"effort": EFFORT}, "max_output_tokens": 2000,
            "service_tier": TIER, "prompt_cache_key": "is-rule-v1"}
    last = None
    for attempt in range(4):
        throttle()
        try:
            r = requests.post(API, headers={"Authorization": f"Bearer {KEY}"},
                              json=body, timeout=180)
            if r.status_code == 200:
                resp = r.json()
                txt = resp.get("output_text") or "\n".join(
                    c["text"] for it in resp.get("output", [])
                    for c in (it.get("content") or []) if c.get("text"))
                m = re.search(r"\[.*\]", txt, re.S)
                v = {int(d["ID"]): bool(d["is_rule"]) for d in json.loads(m.group(0))} if m else {}
                got = {r_["i"]: v[r_["i"]] for r_ in ch if r_["i"] in v}
                if got:
                    with _wlock:
                        for i, b in got.items():
                            _ck.write(json.dumps({"i": i, "is_rule": b}) + "\n")
                        _ck.flush()
                return got, (resp.get("usage") or {}), len(ch) - len(got)
            last = f"{r.status_code} {r.text[:120]}"
        except Exception as e:
            last = repr(e)[:120]
        time.sleep(1.5 * (attempt + 1))
    print(f"  CHUNK FAILED after 4 tries: {last}", flush=True)
    return {}, {}, len(ch)

t0, usage, missing, n_done = time.time(), [], 0, 0
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    futs = [ex.submit(one, c) for c in chunks]
    for n, f in enumerate(as_completed(futs), 1):
        got, u, miss = f.result()
        done.update(got); usage.append(u); missing += miss; n_done += len(got)
        if n % 100 == 0 or n == len(chunks):
            dt = time.time() - t0
            cost = sum((x.get("cost") or {}).get("total_cost", 0) for x in usage)
            print(f"  {n:,}/{len(chunks):,} calls · {len(done):,} rows · {n/dt:.1f} rps "
                  f"· ${cost:.2f} · {dt/60:.1f}m elapsed", flush=True)
_ck.close()

dt = time.time() - t0
cost = sum((x.get("cost") or {}).get("total_cost", 0) for x in usage)
tin = sum(x.get("input_tokens", 0) for x in usage)
cch = sum((x.get("input_tokens_details") or {}).get("cached_tokens", 0) for x in usage)

out = [{"rule ID": r["rule ID"], "rule_clause": r["rule_clause"],
        "context": r["context"], "is_rule": done.get(r["i"])} for r in rows]
json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)

judged = [o for o in out if o["is_rule"] is not None]
yes = sum(1 for o in judged if o["is_rule"])
print(f"\nDONE  {len(judged):,}/{len(rows):,} judged ({len(rows)-len(judged)} unresolved) in {dt/60:.1f} min")
print(f"is_rule: {yes:,} yes / {len(judged)-yes:,} no ({yes/max(len(judged),1):.1%})")
print(f"cost ${cost:.2f} · cache {cch/max(tin,1):.0%} · ${cost/max(len(judged),1)*1000:.3f} per 1k rows")
print(f"→ {OUT}")
