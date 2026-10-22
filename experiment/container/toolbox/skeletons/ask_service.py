#!/usr/bin/env python3
"""Asks the root service (service.py) about one action; run by an agent-side part (a framework hook, a command
wrapper, a git hook).   ask_service.py <rule id> < action.json
Exit 0: allowed. Exit 1: refused, and the service's message on stderr."""
import json
import socket
import sys

SOCK = "/run/enforce/<name>.sock"
request = {"rule": sys.argv[1], "action": json.load(sys.stdin)}
try:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(30)
        s.connect(SOCK)
        s.sendall((json.dumps(request, ensure_ascii=False) + "\n").encode())
        reply = json.loads(s.makefile(encoding="utf-8").readline())
except (OSError, ValueError) as e:
    print(f"{sys.argv[1]}: the enforcement service does not answer ({e})", file=sys.stderr)
    sys.exit(1)                                     # <when the service is down: refuse (exit 1), or let pass (exit 0)>
if not reply.get("allowed"):
    print(reply.get("message") or f"{sys.argv[1]}: refused", file=sys.stderr)
    sys.exit(1)
