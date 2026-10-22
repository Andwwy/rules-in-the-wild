"""Feeds test cases to the hooks that the agent's Claude Code will load, the way Claude Code would call them, and prints
the verdicts as JSON (design_process.md, point 86). Standard library only. Two uses: scripts/score_phase0.py runs it in
a copy of a run's container with the task's held-out cases (no agent sees them); runner.py runs it in the live
container to check a binding node with phase 0's own fixtures, and restores /workspace afterwards.

    python3 phase0_probe.py cases.json

For each case (the clean project, and one case per rule that breaks only that rule), in a fresh /workspace:
  tool   the agent writes the case's files with Write: PreToolUse Write, the file is written, PostToolUse Write; then Stop
  shell  a shell command writes them: PreToolUse Bash, the files are written, PostToolUse Bash; then Stop
  reply  only the turn's reply differs: Stop
Each hook whose event and matcher fit, from every settings file the agent loads in /workspace (managed, project local,
project, the agent's own), is run as `agent`, with Claude Code's input on stdin, CLAUDE_PROJECT_DIR=/workspace, cwd
/workspace, and /opt/enforce/tool-installs/bin on its PATH only if the agent's PATH has it (it does not). Its verdict is read as Claude Code reads it: exit 2, a
JSON `decision: block` / `permissionDecision: deny`, or `continue: false` (which ends the turn) flags; `updatedInput`
or a changed file fixes; else it passes.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import uuid

SETTINGS = ["/etc/claude-code/managed-settings.json", "/workspace/.claude/settings.local.json",
            "/workspace/.claude/settings.json", "/home/agent/.claude/settings.json"]
WS, USER = "/workspace", "agent"
KEEP = {".claude", "CLAUDE.md"}                                 # the project's settings and rules stay in a fresh workspace


def load_settings() -> dict:
    """Every settings file the agent loads, their hooks merged (Claude Code merges hooks across scopes)."""
    merged: dict = {"hooks": {}}
    paths = [os.path.join("/etc/claude-code/managed-settings.d", f) for f in sorted(os.listdir("/etc/claude-code/managed-settings.d"))
             if f.endswith(".json")] if os.path.isdir("/etc/claude-code/managed-settings.d") else []
    for path in SETTINGS[:1] + paths + SETTINGS[1:]:
        try:
            data = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for event, groups in (data.get("hooks") or {}).items() if isinstance(data, dict) else []:
            merged["hooks"].setdefault(event, []).extend(groups if isinstance(groups, list) else [])
    return merged


def hooks_for(settings: dict, event: str, tool: str | None) -> list[dict]:
    out = []
    for group in (settings.get("hooks") or {}).get(event, []):
        m = group.get("matcher")
        if tool is not None and m not in (None, "", "*"):
            parts = [x.strip() for x in re.split(r"[|,]", m)] if re.fullmatch(r"[\w\s,|-]+", m) else None
            if not (tool in parts if parts else re.fullmatch(m, tool)):
                continue
        out += [h for h in group.get("hooks", []) if h.get("type", "command") == "command"]
    return out


def run_hook(h: dict, inp: dict) -> dict:
    cmd = h["command"] + ("" if not h.get("args") else " " + " ".join(map(str, h["args"])))
    try:
        done = subprocess.run(["runuser", "-u", USER, "--", "env", f"CLAUDE_PROJECT_DIR={WS}", "HOME=/home/agent",
                               "PATH=/usr/local/bin:/usr/bin:/bin", "sh", "-c", cmd], input=json.dumps(inp), capture_output=True, text=True, cwd=WS,
                              timeout=min(int(h.get("timeout") or 60), 300))
    except subprocess.TimeoutExpired:
        return {"verdict": "timeout"}
    out, err = done.stdout or "", done.stderr or ""
    try:
        j = json.loads(out) if out.strip().startswith("{") else {}
    except Exception:
        j = {}
    hso = j.get("hookSpecificOutput") or {} if isinstance(j, dict) else {}
    # A JSON object decides whatever the exit code (exit 2 blocks anyway), as Claude Code 2.1.199 does: a PreToolUse deny
    # and a top-level block at exit 1 were obeyed; a field in the wrong place (`decision` inside `hookSpecificOutput`
    # at Stop) was not (design_process.md, point 101)
    if done.returncode == 2 or j.get("decision") == "block" or hso.get("permissionDecision") == "deny":
        return {"verdict": "flag", "msg": (err or j.get("reason") or hso.get("permissionDecisionReason") or out)[:2000]}
    if done.returncode == 0 and isinstance(j, dict) and j.get("continue") is False:      # ends the agent's turn
        return {"verdict": "flag", "stop": True, "msg": str(j.get("stopReason") or out)[:300]}
    if done.returncode == 0 and "updatedInput" in hso:
        return {"verdict": "fix", "msg": str(hso.get("additionalContext") or "")[:300]}
    if done.returncode != 0:
        return {"verdict": "error", "msg": f"exit {done.returncode}: {(err or out)[-200:]}"}
    return {"verdict": "pass"}


def fresh_workspace() -> None:
    for name in [n for n in os.listdir(WS) if n not in KEEP]:
        p = os.path.join(WS, name)
        shutil.rmtree(p) if os.path.isdir(p) and not os.path.islink(p) else os.remove(p)


def put(rel: str, data: bytes) -> None:
    p = os.path.join(WS, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)
    subprocess.run(["chown", f"{USER}:{USER}", p], check=True)


def transcript(reply: str, sid: str) -> str:
    path = f"/tmp/probe-{sid}.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user", "sessionId": sid, "message": {"role": "user", "content": "请继续。"}}, ensure_ascii=False) + "\n")
        f.write(json.dumps({"type": "assistant", "sessionId": sid, "message": {"role": "assistant", "model": "claude-haiku-4-5",
                            "content": [{"type": "text", "text": reply}]}}, ensure_ascii=False) + "\n")
    os.chmod(path, 0o644)
    return path


def bytes_of(spec) -> bytes:
    if isinstance(spec, str):
        return spec.encode("utf-8")
    return spec["text"].encode(spec.get("encoding", "utf-8"))


def run_case(settings: dict, base_files: dict, case: dict, reply_ok: str, channel: str) -> list[dict]:
    """One case through one channel; every hook verdict in order."""
    sid = str(uuid.uuid4())
    fresh_workspace()
    files = {**base_files, **case.get("files", {})}
    reply = case.get("reply", reply_ok)
    common = {"session_id": sid, "prompt_id": "p1", "cwd": WS, "permission_mode": "bypassPermissions",
              "transcript_path": transcript(reply, sid)}
    rows = []

    def fire(event: str, tool: str | None, extra: dict) -> None:
        for n, h in enumerate(hooks_for(settings, event, tool)):
            r = run_hook(h, {**common, "hook_event_name": event, **({"tool_name": tool} if tool else {}), **extra})
            rows.append({"event": event, "tool": tool, "hook": h["command"][-80:], **r})

    if channel == "reply":
        for rel, spec in base_files.items():
            put(rel, bytes_of(spec))
    elif channel == "tool":
        for rel, spec in files.items():
            path, data = f"{WS}/{rel}", bytes_of(spec)
            text = data.decode("utf-8", errors="replace")
            tid = f"toolu_{uuid.uuid4().hex[:20]}"
            ti = {"file_path": path, "content": text}
            fire("PreToolUse", "Write", {"tool_input": ti, "tool_use_id": tid})
            put(rel, data)
            fire("PostToolUse", "Write", {"tool_input": ti, "tool_use_id": tid,
                                          "tool_response": {"type": "create", "filePath": path, "content": text}})
    else:                                                      # shell: one command writes every file
        tid = f"toolu_{uuid.uuid4().hex[:20]}"
        ti = {"command": " && ".join(f"cat > {rel} <<'EOF' ... EOF" for rel in files), "description": "write the files"}
        fire("PreToolUse", "Bash", {"tool_input": ti, "tool_use_id": tid})
        for rel, spec in files.items():
            put(rel, bytes_of(spec))
        fire("PostToolUse", "Bash", {"tool_input": ti, "tool_use_id": tid,
                                     "tool_response": {"stdout": "", "stderr": "", "interrupted": False}})
    fire("Stop", None, {"stop_hook_active": False, "last_assistant_message": reply})
    return rows


def main(path: str) -> None:
    spec = json.load(open(path, encoding="utf-8"))
    settings = load_settings()
    out = {"hooks": sum(len(g.get("hooks", [])) for gs in (settings.get("hooks") or {}).values() for g in gs), "cases": []}
    for case in [{"rule": None, "name": "clean project", **spec["pass"]}, *spec["cases"]]:
        channels = case.get("channels") or (["reply"] if "reply" in case and not case.get("files") else ["tool", "shell"])
        for ch in channels:
            out["cases"].append({"rule": case.get("rule"), "name": case.get("name"), "channel": ch,
                                 "rows": run_case(settings, spec["pass"]["files"], case, spec["pass"]["reply"], ch)})
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
