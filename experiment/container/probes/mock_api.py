"""A scripted stand-in for the Anthropic Messages API, for chain checks with no model calls (`runner.py --mock`). Runs
inside the container; standard library only. Ported from the pilot's toolbox/tests/claude-code/mock_api.mjs.

    python3 -I mock_api.py <scenario.json> <api-log.jsonl>        listens on 127.0.0.1:8765

scenario.json: {"scripts": [{"match": "<text in a user prompt>", "actions": [{"tool": "Bash", "input": {...}} |
{"text": "..."}, ...]}, ...]}. A main-loop request (one with tools) gets the next action of the script whose `match` is
in the last user prompt that has one; the action's index is the number of assistant messages after that prompt. A
request without tools (a side call) gets "ok". Every request is logged with the end of its last user message, so the
check can see what the hooks told the agent, and the names of the tools Claude Code offered (`tools`; once, their full schemas: `tool_schemas`).
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SCRIPTS = json.load(open(sys.argv[1], encoding="utf-8"))["scripts"]
LOG = sys.argv[2]
COUNT = [0]
SCHEMAS_LOGGED = [False]


def texts(m):
    c = m.get("content")
    if isinstance(c, str):
        return [c]
    return [b.get("text", "") for b in c or [] if isinstance(b, dict) and b.get("type") == "text"]


def pick(body):
    if not body.get("tools"):
        return {"text": "ok", "side": True}
    msgs = body.get("messages") or []
    at, script = -1, None
    for k, m in enumerate(msgs):
        if m.get("role") != "user":
            continue
        joined = "\n".join(texts(m))
        for s in SCRIPTS:
            if s["match"] in joined:
                at, script = k, s
    if script is None:
        return {"text": "(no script for this prompt)", "script": None, "idx": 0}
    idx = sum(1 for m in msgs[at + 1:] if m.get("role") == "assistant")
    acts = script["actions"]
    return {**(acts[idx] if idx < len(acts) else {"text": "(script ended)"}), "script": script["match"], "idx": idx}


def reply(action, model, stream):
    COUNT[0] += 1
    n = COUNT[0]
    mid = f"msg_mock_{n}"
    if action.get("tool"):
        block = {"type": "tool_use", "id": f"toolu_mock_{n}", "name": action["tool"], "input": action["input"]}
        start, delta = {**block, "input": {}}, {"type": "input_json_delta", "partial_json": json.dumps(action["input"])}
    else:
        block = {"type": "text", "text": action["text"]}
        start, delta = {"type": "text", "text": ""}, {"type": "text_delta", "text": action["text"]}
    stop = "tool_use" if action.get("tool") else "end_turn"
    usage = {"input_tokens": 10, "output_tokens": 5}
    if not stream:
        return "application/json", json.dumps({"id": mid, "type": "message", "role": "assistant", "model": model,
                                               "content": [block], "stop_reason": stop, "stop_sequence": None, "usage": usage})
    ev = []
    push = lambda t, d: ev.append(f"event: {t}\ndata: {json.dumps({'type': t, **d})}\n\n")
    push("message_start", {"message": {"id": mid, "type": "message", "role": "assistant", "model": model, "content": [],
                                       "stop_reason": None, "stop_sequence": None, "usage": usage}})
    push("content_block_start", {"index": 0, "content_block": start})
    push("content_block_delta", {"index": 0, "delta": delta})
    push("content_block_stop", {"index": 0})
    push("message_delta", {"delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"output_tokens": 5}})
    push("message_stop", {})
    return "text/event-stream", "".join(ev)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("content-length") or 0))
        try:
            body = json.loads(raw or b"{}")
        except Exception:
            body = {}
        if "count_tokens" in self.path:
            return self.send(200, "application/json", '{"input_tokens": 10}')
        if "/v1/messages" not in self.path:
            return self.send(404, "application/json", "{}")
        action = pick(body)
        last = (body.get("messages") or [{}])[-1]
        with open(LOG, "a", encoding="utf-8") as f:
            if body.get("tools") and not SCHEMAS_LOGGED[0]:     # once: every tool Claude Code offers, as it offers it
                SCHEMAS_LOGGED[0] = True
                f.write(json.dumps({"tool_schemas": body["tools"]}, ensure_ascii=False) + "\n")
            f.write(json.dumps({"side": bool(action.get("side")), "script": action.get("script"), "idx": action.get("idx"),
                                "tools": [t.get("name") for t in body.get("tools") or []],
                                "answer": f"{action['tool']} {json.dumps(action['input'], ensure_ascii=False)[:200]}" if action.get("tool") else action["text"],
                                "last_user": json.dumps(last.get("content"), ensure_ascii=False)[-3000:]}, ensure_ascii=False) + "\n")
        ctype, payload = reply(action, body.get("model") or "mock", bool(body.get("stream")))
        self.send(200, ctype, payload)

    def send(self, code, ctype, payload):
        data = payload.encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
