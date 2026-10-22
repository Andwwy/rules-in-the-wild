#!/usr/bin/env python3
"""A root service: decides the agent's actions and keeps their history where the agent cannot change it.
Start it as root so that it keeps running:
    nohup python3 service.py > /var/lib/enforce-state/<name>/service.log 2>&1 &
The agent-side parts (a framework hook, a command wrapper, a git hook) ask it with ask_service.py: one JSON line,
{"rule": "<rule id>", "action": {...}}; the answer: {"allowed": true|false, "message": "..."}."""
import json
import os
import socketserver
import threading
import time

SOCK = "/run/enforce/<name>.sock"
STATE = "/var/lib/enforce-state/<name>"            # root only: the agent can neither read nor change it
LOCK = threading.Lock()


def decide(request: dict, history: list[dict]) -> tuple[bool, str]:
    """<the rule>: (True, "") to allow; else (False, what to tell the agent: the rule, where, what to change).
    `history`: the earlier requests and decisions, oldest first."""
    return True, ""


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            request = json.loads(self.rfile.readline() or b"{}")
        except ValueError:
            request = {}
        with LOCK:
            path = f"{STATE}/history.jsonl"
            history = [json.loads(line) for line in open(path, encoding="utf-8")] if os.path.exists(path) else []
            allowed, message = decide(request, history)
            trial = os.path.exists("/run/enforce/trial")          # a `try` trial runs
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"time": time.time(), "request": request, "allowed": allowed, "trial": trial},
                                   ensure_ascii=False) + "\n")
        self.wfile.write((json.dumps({"allowed": allowed, "message": message}, ensure_ascii=False) + "\n").encode())


os.makedirs(STATE, mode=0o700, exist_ok=True)
os.makedirs(os.path.dirname(SOCK), mode=0o755, exist_ok=True)
if os.path.exists(SOCK):
    os.remove(SOCK)
server = socketserver.ThreadingUnixStreamServer(SOCK, Handler)
os.chmod(SOCK, 0o666)                                              # the agent's parts may ask; only root keeps state
server.serve_forever()
