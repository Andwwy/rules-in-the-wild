#!/usr/bin/env python3
"""phase 0's way to try its enforcement as the agent will meet it (arms B and C; PROTOCOL.md). Copied into the
container as /opt/enforce-harness/try; root only; uses only python3's standard library.

    try --check            the hooks in the agent's settings in the form Claude Code reads, the entries it would drop,
                           and what Claude Code says about the settings (no model call)
    try "<a request>"      the agent's Claude Code, once, as `agent`, in /workspace, with the enforcement as it is
                           (nothing is installed: the agent loads whatever settings phase 0 left where Claude Code looks):
                           prints the hooks in the form Claude Code reads (as --check), what it says about the
                           settings, the agent's actions, each hook's outcome
                           as the agent's transcript records it, and the reply (model calls)

While a trial runs, /run/enforce/trial exists and the trial agent's programs have ENFORCE_TRIAL=1 in their environment,
so phase 0's watchers and services can tell trial actions from the task's. Afterwards /workspace is restored in place
from a copy taken before, and the trial's own session files are removed. Nothing outside /workspace and the trial's
session is touched: no settings are installed anywhere (design_process.md, point 81). One `try` runs at a time: a second
waits for the first (phase 0's sessions can run side by side, point 92).
"""
from __future__ import annotations

import fcntl
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import uuid

NOTE, USER, HOME, WORKSPACE = "/opt/agent/environment.md", "agent", "/home/agent", "/workspace"
THINKING = ["--thinking", "adaptive", "--effort", "max"]
SAVED = "/tmp/try-workspace.tar"
TRIAL = "/run/enforce/trial"                       # exists while a trial runs; the trial agent has ENFORCE_TRIAL=1
LOCK = "/run/enforce/try.lock"                     # one try at a time: they share /workspace and the session folder
PROJECTS = f"{HOME}/.claude/projects/-workspace"


MODELS = ("ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL")


def agent_model() -> dict:
    """The task agent's model for a trial (ENFORCE_AGENT_MODEL, set by the runner), when phase 0 runs another model."""
    m = os.environ.get("ENFORCE_AGENT_MODEL")
    return {k: m for k in MODELS} if m else {}


def as_agent(args: list[str], cwd: str, stdin: str | None, timeout: int, env: dict | None = None):
    try:
        return subprocess.run(["runuser", "-u", USER, "--", "env", f"HOME={HOME}", f"USER={USER}", f"LOGNAME={USER}",
                               *[f"{k}={v}" for k, v in (env or {}).items()], *args],
                              input=stdin, capture_output=True, text=True, cwd=cwd, timeout=timeout)
    except subprocess.TimeoutExpired as err:
        out = lambda b: b.decode(errors="replace") if isinstance(b, bytes) else (b or "")
        return subprocess.CompletedProcess(args, 124, out(err.stdout), out(err.stderr) + f"\n(timed out after {timeout} s)")


class NoModel(http.server.BaseHTTPRequestHandler):
    """Answers every model call at once with HTTP 400, which Claude Code does not retry: it starts, loads its
    settings, says what it thinks of them, and stops."""
    def do_POST(self):
        body = json.dumps({"type": "error", "error": {"type": "invalid_request_error",
                                                      "message": "try --check: no model here"}}).encode()
        self.send_response(400); self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body))); self.end_headers(); self.wfile.write(body)
    do_GET = do_POST
    def log_message(self, *args):
        pass


def settings_lines(text: str) -> list[str]:
    lines = text.splitlines()
    keep = set()
    for i, line in enumerate(lines):
        low = line.lower()
        if "settings" in low or "schema" in low or "invalid" in low:
            keep.update(range(i, min(i + 3, len(lines))))
    return [lines[i] for i in sorted(keep)]


def sessions() -> set[str]:
    try:
        return set(os.listdir(PROJECTS))
    except OSError:
        return set()


def forget(before: set[str]) -> None:
    """Remove the session files that a trial or a check added."""
    for name in sessions() - before:
        p = os.path.join(PROJECTS, name)
        shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)


def loaded() -> list[str]:
    """The hooks in the agent's settings as Claude Code's documented schema reads them (environment.py --settings), and
    the entries it would drop: in `claude -p`, Claude Code drops a broken entry, or the whole `hooks` field, without a
    word, so its own output cannot show it."""
    done = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "environment.py"),
                           "--settings"], capture_output=True, text=True)
    try:
        got = json.loads(done.stdout)
    except Exception:
        return [f"(the settings could not be read: {(done.stdout + done.stderr)[-300:]})"]
    out = [f"the agent's settings hold {len(got['hooks'])} hooks in the form Claude Code reads"
           + "".join(f"\n  {h['event']} {h.get('matcher') or ''}: {h.get('command')} {' '.join(h.get('args') or [])}".rstrip()
                     for h in got["hooks"])]
    out += [f"not in that form, so Claude Code drops it (and may drop the whole `hooks` field of {m['path']}): "
            f"{m['event']}: {one_line(json.dumps(m['entry'], ensure_ascii=False), 300)} ({m['problem']})"
            for m in got.get("malformed") or []]
    out += [f"{f['path']}: {f['error']}" for f in got["files"] if f.get("error")]
    return out


def check() -> None:
    before = sessions()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), NoModel)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    done = as_agent(["claude", "-p", "hi", "--max-turns", "1"], WORKSPACE, None, 120,
                    {"ANTHROPIC_BASE_URL": f"http://127.0.0.1:{server.server_address[1]}", "ANTHROPIC_API_KEY": "x"})
    server.shutdown()
    forget(before)
    for line in loaded():
        print(line)
    lines = settings_lines(done.stdout + "\n" + done.stderr)
    print("Claude Code on the settings:" if lines else "Claude Code reported nothing about the settings.")
    for line in lines:
        print(f"  {line}")


def one_line(text: str, n: int = 2000) -> str:
    """A message on one line, so a reader of this output sees every rule it names."""
    return " ⏎ ".join(str(text).split("\n"))[:n]


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    return " ".join(str(b.get("text") or b.get("content") or "") for b in content or [] if isinstance(b, dict))


def trial(request: str) -> None:
    sid, before = str(uuid.uuid4()), sessions()
    os.makedirs(os.path.dirname(TRIAL), exist_ok=True)
    open(TRIAL, "w").write(sid + "\n")                  # while it exists, a trial runs (design_process.md, point 73)
    try:
        done = as_agent(["claude", "-p", "--session-id", sid, "--dangerously-skip-permissions",
                         "--append-system-prompt-file", NOTE, *THINKING, "--max-turns", "100", "--output-format", "json"],
                        WORKSPACE, request, 900, {"ENFORCE_TRIAL": "1", **agent_model()})
    finally:
        os.remove(TRIAL)
    for line in loaded():
        print(line)
    lines = settings_lines(done.stderr)
    if lines:
        print("Claude Code on the settings:")
        for line in lines:
            print(f"  {line}")
    print("the agent's actions and the hooks' outcomes:")
    try:
        for raw in open(f"{PROJECTS}/{sid}.jsonl", encoding="utf-8"):
            d = json.loads(raw)
            att = d.get("attachment") or {}
            if att.get("type", "").startswith("hook"):
                be = att.get("blockingError")
                said = (be.get("blockingError") if isinstance(be, dict) else be) or att.get("stderr") \
                    or att.get("content") or att.get("stdout") or ""
                print(f"  [{att['type']}] {att.get('hookEvent') or att.get('hookName') or ''} exit {att.get('exitCode', '')}"
                      f"{': ' + one_line(said) if said and said != '{}' else ''}")
            content = (d.get("message") or {}).get("content")
            if d.get("type") == "user" and "hook" in text_of(content).lower() and "tool_result" not in json.dumps(content):
                print(f"  [hook feedback] {one_line(text_of(content))}")
            for b in content if isinstance(content, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    inp = b.get("input") or {}
                    print(f"  {b['name']}: {(inp.get('file_path') or inp.get('command') or json.dumps(inp))[:200]}")
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                    print(f"    -> error: {one_line(text_of(b.get('content')))}")
    except OSError:
        print("  (no transcript)")
    try:
        result = json.loads(done.stdout.strip().splitlines()[-1])
        print(f"the agent's reply: {str(result.get('result'))[:1500]}")
    except Exception:
        print(f"the agent's output: {(done.stdout + done.stderr)[-1500:]}")
    forget(before)


def main(argv: list[str]) -> int:
    if os.geteuid() != 0:
        print("try runs as root")
        return 2
    request = None if argv[:1] == ["--check"] else " ".join(argv).strip()
    if request == "":
        print(__doc__)
        return 2
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    lock = open(LOCK, "w")
    fcntl.flock(lock, fcntl.LOCK_EX)                # released when this process ends
    if request is None:
        check()
        return 0
    subprocess.run(["tar", "-C", "/", "-cpf", SAVED, WORKSPACE.lstrip("/")], check=True)
    try:
        trial(request)
    finally:                                       # in place: the folder itself stays
        for name in os.listdir(WORKSPACE):
            p = os.path.join(WORKSPACE, name)
            try:                                   # an immutable file (chattr +i) cannot go, nor change: it stays
                shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) and not os.path.islink(p) else os.remove(p)
            except OSError:
                pass
        subprocess.run(["tar", "-C", "/", "-xpf", SAVED], check=False, capture_output=True)
        os.remove(SAVED)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
