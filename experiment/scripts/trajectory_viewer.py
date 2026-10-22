"""Build agents/<agent>/trajectories.html: every agent action of runner.py's runs, by phase and turn, in one page.

    uv run --project "dataset/MTAC bench/base agent" python scripts/trajectory_viewer.py                 the latest run of each arm of 46, 91
    uv run --project "dataset/MTAC bench/base agent" python scripts/trajectory_viewer.py <run dir> ...  these runs

For each run: the container setup; phase 0 (root; B and C): the system prompt (Claude Code's own, shown as a tag, plus
prompts/system.md and the arm's parts), then each rule message (B: the rule; C: the rule with Jev's enforcer, trigger and target and the
notes), with the agent's actions in order (tool calls, files written or edited, `try` trials, thinking) and its reply;
the harness's install (hooks, Claude Code's verdict on the settings, what changed); the task (`agent`): the system
prompt (Claude Code's own, the task note, CLAUDE.md), then each turn: MTAC's request, the actions, hook verdicts, the
reply that was scored and the score per rule. Long texts are cut (the page says where). The page is one file, its data
inline; trajectory_viewer.html is its template.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
import paths                                                # noqa: E402

paths.use("agentprobe")
import mtac_locate, score_runs                            # noqa: E402
from benchmarks.mtacifbench.models import MTACIFBenchQuestion       # noqa: E402

TEMPLATE = paths.SCRIPTS / "trajectory_viewer.html"
MTAC = paths.MTAC_DATA
OUT = paths.AGENTS / paths.DEFAULT_AGENT / "trajectories.html"
ARM_NAME = {a: a for a in paths.ARMS}                                # the arm folders are the arms' names
HEREDOC = re.compile(r"(?:cat|tee)\s+(?:-a\s+)?>{0,2}\s*['\"]?([/\w.\-]+)['\"]?\s*<<")


def cut(text, n: int) -> str:
    text = "" if text is None else str(text)
    return text if len(text) <= n else text[:n] + f"\n… ({len(text) - n} more characters not shown)"


def lines_of(path: Path) -> list[dict]:
    out = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            out.append(json.loads(raw))
        except Exception:
            pass
    return out


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") if isinstance(b, dict) and b.get("type") == "text" else
                         (b if isinstance(b, str) else "") for b in content)
    return ""


def tool_event(b: dict, phase: int) -> dict:
    name, inp = b.get("name", ""), b.get("input") or {}
    ev = {"k": "tool", "name": name, "as": "agent" if phase == 1 else "root"}
    if name == "Bash":
        cmd = inp.get("command", "")
        ev["summary"] = cmd.strip().splitlines()[0][:160] if cmd.strip() else "(empty)"
        ev["detail"] = cut(cmd, 4000)
        if phase == 0 and "/opt/enforce-harness/try" in cmd:
            ev["as"], ev["try"] = "agent (try)", True
        elif phase == 0 and "runuser -u agent" in cmd:
            ev["as"] = "agent (runuser)"
        writes = HEREDOC.findall(cmd)
        if writes:
            ev["files"] = [{"path": p, "op": "write (shell)"} for p in writes]
    elif name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = inp.get("file_path") or inp.get("notebook_path") or ""
        ev["summary"] = path
        ev["files"] = [{"path": path, "op": "write" if name == "Write" else "edit"}]
        if name == "Write":
            ev["detail"] = cut(inp.get("content", ""), 6000)
        elif name == "Edit":
            ev["detail"] = f"--- old\n{cut(inp.get('old_string', ''), 2500)}\n+++ new\n{cut(inp.get('new_string', ''), 2500)}"
        else:
            ev["detail"] = cut(json.dumps(inp, ensure_ascii=False, indent=1), 4000)
    elif name in ("Read", "Glob", "Grep", "LS"):
        ev["summary"] = inp.get("file_path") or inp.get("pattern") or inp.get("path") or ""
        ev["detail"] = cut(json.dumps(inp, ensure_ascii=False), 800)
    elif name == "Skill":
        ev["summary"] = f"{inp.get('skill', '')} {inp.get('args', '')}"[:160]
        ev["detail"] = cut(json.dumps(inp, ensure_ascii=False), 1500)
    elif name == "TodoWrite":
        todos = inp.get("todos") or []
        ev["summary"] = f"{len(todos)} items"
        ev["detail"] = "\n".join(f"[{t.get('status', '')}] {t.get('content', '')}" for t in todos)[:3000]
    else:
        ev["summary"] = cut(json.dumps(inp, ensure_ascii=False), 160)
        ev["detail"] = cut(json.dumps(inp, ensure_ascii=False, indent=1), 2000)
    return ev


def hms(d: dict) -> str:
    """The time of a transcript entry, HH:MM:SS (UTC)."""
    return str(d.get("timestamp") or "")[11:19]


def events(lines: list[dict], phase: int) -> list[dict]:
    out, by_id = [], {}
    for d in lines:
        n_before = len(out)
        t, m = d.get("type"), d.get("message") or {}
        if d.get("isCompactSummary"):
            out.append({"k": "compact", "text": cut(text_of(m.get("content")), 2000)})
            continue
        if t == "assistant" and isinstance(m.get("content"), list):
            synthetic = m.get("model") == "<synthetic>"
            for b in m["content"]:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and b.get("text", "").strip():
                    out.append({"k": "text", "text": cut(b["text"], 4000), "synthetic": synthetic})
                elif b.get("type") == "thinking" and b.get("thinking", "").strip():
                    out.append({"k": "think", "text": cut(b["thinking"], 3000)})
                elif b.get("type") == "tool_use":
                    ev = tool_event(b, phase)
                    by_id[b.get("id")] = ev
                    out.append(ev)
        elif t == "user":
            c = m.get("content")
            if isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in by_id:
                        ev = by_id[b["tool_use_id"]]
                        ev["result"] = cut(text_of(b.get("content")) or json.dumps(b.get("content"), ensure_ascii=False), 2500)
                        ev["error"] = bool(b.get("is_error"))
            elif isinstance(c, str) and c.startswith("Stop hook feedback"):
                out.append({"k": "hook", "event": "Stop", "verdict": "block", "msg": cut(c, 1500)})
        elif t == "attachment":
            a = d.get("attachment") or {}
            if str(a.get("type", "")).startswith("hook_"):
                msg = a.get("stderr") or (a.get("blockingError") or {}).get("blockingError") or a.get("content") or a.get("message") or ""
                out.append({"k": "hook", "event": a.get("hookName") or a.get("hookEvent") or "",
                            "verdict": {"hook_blocking_error": "block", "hook_non_blocking_error": "error"}.get(a["type"], a["type"]),
                            "msg": cut(msg, 1500), "exit": a.get("exitCode")})
        for ev in out[n_before:]:
            ev["t"] = hms(d)
    return out


def last_reply(evs: list[dict]) -> str:
    for ev in reversed(evs):
        if ev["k"] == "text" and not ev.get("synthetic"):
            return ev["text"]
    return ""


def phase0(run: Path, arm: str, tid: int) -> dict | None:
    s1 = run / "phase0"
    if not s1.is_dir():
        return None
    # the inputs the run got (runner.py keeps a copy); for runs before that, the task's current inputs
    folder = s1 / "translation" if (s1 / "translation" / "messages.json").exists() else paths.arm_inputs(tid, arm)
    # a phase 0 written by hand (C-ideal, point 107) has no messages: its hooks name their rules (R<n>) in what they say
    msgs = json.loads((folder / "messages.json").read_text(encoding="utf-8")) if (folder / "messages.json").exists() else []
    transcripts = sorted(s1.glob("*.jsonl"))       # one session, or one per node of C's compiled plan (point 87)
    lines = sorted((d for t in transcripts for d in lines_of(t)), key=lambda d: str(d.get("timestamp", "")))
    starts = [i for i, d in enumerate(lines) if d.get("type") == "user" and not d.get("isMeta")
              and not d.get("isCompactSummary") and isinstance((d.get("message") or {}).get("content"), str)
              and d["message"]["content"].startswith(("Rule R", "These rules are for"))]   # a rule, or a batch (point 82)
    rules = []
    for k, m in enumerate(msgs):
        text = m["text"]
        head, _, rest = text.partition("\n# ")
        notes = [("# " + part).split("\n", 1) for part in ("# " + rest).split("\n# ") if part.strip()] if rest else []
        field = lambda name: (re.search(rf"^- {name}: (.+)$", head, re.M) or [None, None])[1]
        evs = events(lines[starts[k] + 1:starts[k + 1]] if k + 1 < len(starts) else lines[starts[k] + 1:], 0) \
            if k < len(starts) else []
        meta = {}
        res_path = next(iter([*s1.glob(f"message_{k + 1}.json"), *s1.glob(f"message_{k + 1}.*.json")]), None)
        if res_path:
            res = json.loads(res_path.read_text(encoding="utf-8")).get("result") or {}
            meta = {"seconds": round((res.get("duration_ms") or 0) / 1000), "model_turns": res.get("num_turns"),
                    "cost": res.get("total_cost_usd")}
        ids = m.get("rules") or [m["rule"]]                # a batch of rules (point 82), or one rule
        first = re.search(r"^Rule R\d+: (.+)$", head, re.M)
        rules.append({"rule": ids[0] if len(ids) == 1 else f"{ids[0]}–{ids[-1]}", "rules": ids,
                      "text": first[1] if len(ids) == 1 and first else f"{len(ids)} rules in one message",
                      "t": hms(lines[starts[k]]) if k < len(starts) else "", "full": text,
                      "message": head.strip(), "enforcer": field("Enforcer"), "trigger": field("Trigger"),
                      "target": field("Target"),
                      "notes": [{"title": n[0].lstrip("# ").strip(), "body": cut(n[1] if len(n) > 1 else "", 4000)} for n in notes],
                      "events": evs, "reply": last_reply(evs), **meta})
    install = json.loads((s1 / "install.json").read_text(encoding="utf-8")) if (s1 / "install.json").exists() else {}
    env = json.loads((s1 / "environment.json").read_text(encoding="utf-8") or "{}") if (s1 / "environment.json").exists() else {}
    ws = json.loads((s1 / "workspace.json").read_text(encoding="utf-8")) if (s1 / "workspace.json").exists() else {}
    files = json.loads((s1 / "files.json").read_text(encoding="utf-8") or "{}") if (s1 / "files.json").exists() else {}
    hooks = installed_hooks(install)
    segments = [tool_inputs(lines[starts[k] + 1:starts[k + 1]] if k + 1 < len(starts) else lines[starts[k] + 1:])
                for k in range(len(starts))]
    contents_written = written_files(lines)
    contents = dict(contents_written)
    contents.update({f"/opt/enforce/{k}": v for k, v in files.items() if isinstance(v, str) and not v.startswith("(")})
    rule_of_hook = hook_rules(hooks, segments, [r["rule"] for r in rules], contents,
                              [i for r in rules for i in r["rules"]])
    system = s1 / "system.md" if (s1 / "system.md").exists() else folder / "system.md"   # as sent, its framework section in
    return {"system": system.read_text(encoding="utf-8") if system.exists() else "(phase 0 written by hand: no system prompt)",
            "rules": rules,
            "t0": hms(lines[starts[0]]) if starts else "",
            "extras": phase0_extras(files, env, install, ws, contents_written,
                                    " ".join([h["command"] + " " + " ".join(h.get("args") or []) for h in hooks]
                                             + [contents.get(x, "") for h in hooks for x in re.findall(r"/opt/[\w./-]+\.\w+", h["command"])])),
            "install": {"hooks": [{"n": h["hook"], "rule": rule_of_hook.get(str(h["hook"])), "event": h["event"], "matcher": h.get("matcher"),
                                   "says": hook_says(h["command"] + (" " + " ".join(h["args"]) if h.get("args") else ""), contents),
                                   "command": h["command"] + (" " + " ".join(h["args"]) if h.get("args") else ""),
                                   "form": h.get("form"), "scope": h.get("scope")} for h in hooks],
                        "verdict": install.get("claude_code_on_settings"),
                        "commands_added": install.get("commands_added_for_agent") or [],
                        "workspace": {k: sorted(v) if isinstance(v, (dict, list)) else v for k, v in ws.items()},
                        "packages": env.get("packages_added") or [], "processes": env.get("processes_started") or [],
                        "outside_files": env.get("outside_total"),
                        **own_files(files)}}


def tool_inputs(lines: list[dict]) -> str:
    """The text of every tool call in a part of a transcript (commands, file contents, edits), decoded."""
    out = []
    for d in lines:
        m = d.get("message") or {}
        if d.get("type") == "assistant" and isinstance(m.get("content"), list):
            for b in m["content"]:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    inp = b.get("input") or {}
                    out += [v for v in inp.values() if isinstance(v, str)]
                    out += [json.dumps(e, ensure_ascii=False) for e in inp.get("edits") or []]
    return "\n".join(out)


def installed_hooks(install: dict) -> list[dict]:
    """The agent's command hooks after phase 0: the settings files it left (point 81: `settings`), or, for runs before
    2026-10-21, the harness's install into managed settings (`install`)."""
    return [h for h in ((install.get("settings") or {}).get("hooks") or (install.get("install") or {}).get("hooks") or [])
            if h.get("type", "command") == "command" and h.get("command")]


def hook_rules(hooks: list[dict], segments: list[str], message_ids: list[str], contents: dict | None = None,
               rule_ids: list[str] | None = None) -> dict[str, str]:
    """The policy rule of each installed hook: a script named for a rule (`r3-check.py`, `rule_r3.sh`) names it; else
    the one rule that the hook's script names (R<n>) in its text; else, when each message held one rule, the first
    message whose tool calls wrote the hook's script, or its command as written into the settings. A hook that checks
    several rules gets none here: its messages name the rule (attribute_passes.py)."""
    out, rule_ids = {}, rule_ids or message_ids
    for h in hooks:
        cmd = h["command"] + (" " + " ".join(h["args"]) if h.get("args") else "")
        named = re.search(r"enforce run --rule R(\d+)\b|rule[-_]?r(\d+)\b|(?:^|[/_-])r(\d+)(?=[-_.])", cmd, re.I)
        num = named and (named.group(1) or named.group(2) or named.group(3))
        if num and f"R{num}" in rule_ids:
            out[str(h["hook"])] = f"R{num}"
            continue
        probes = re.findall(r"/opt/enforce[\w./-]*\.\w+", cmd) or [cmd, json.dumps(cmd, ensure_ascii=False)[1:-1]]
        named = {f"R{n}" for p in probes for n in re.findall(r"\bR(\d+)\b", (contents or {}).get(p, ""))} & set(rule_ids)
        if len(named) == 1:
            out[str(h["hook"])] = named.pop()
            continue
        if len(message_ids) == len(segments) and all(i in rule_ids for i in message_ids):   # one rule per message
            for rid, text in zip(message_ids, segments):
                if any(p in text for p in probes):
                    out[str(h["hook"])] = rid
                    break
    return out


def transcript_rows(lines: list[dict], hooks: list[dict]) -> list[dict]:
    """The hooks' outcomes as the agent's transcript records them (point 81: no harness log), in the shape of the old
    log's rows: a blocking hook (attachment hook_blocking_error: its command and message), a refused tool call (a
    tool result with toolDenialKind: a hook's or a permission rule's denial, with its reason), a hook error
    (hook_non_blocking_error) and a hook that passed with output (hook_success). `hook` is the installed hook's number
    when the record names its command, or when only one installed hook could have refused that tool."""
    by_cmd = {h["command"]: str(h["hook"]) for h in hooks}
    tools = {}
    rows = []
    for d in lines:
        ts = str(d.get("timestamp", ""))[:19]
        m = d.get("message") or {}
        if d.get("type") == "assistant" and isinstance(m.get("content"), list):
            for b in m["content"]:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    tools[b.get("id")] = (b.get("name"), (b.get("input") or {}).get("file_path"))
        a = d.get("attachment") or {}
        kind = {"hook_blocking_error": "block", "hook_non_blocking_error": "error", "hook_success": "pass"}.get(a.get("type"))
        if kind:
            be = a.get("blockingError") or {}
            cmd = be.get("command") if isinstance(be, dict) else None
            cmd = cmd or a.get("command")
            msg = (be.get("blockingError") if isinstance(be, dict) else str(be)) or a.get("stderr") or a.get("content") or ""
            event = a.get("hookEvent") or str(a.get("hookName") or "").split(":")[0]
            rows.append({"time": ts, "hook": by_cmd.get(cmd, "?"), "event": event, "verdict": kind,
                         "problem" if kind != "error" else "error": str(msg), "command": cmd})
        if d.get("type") == "user" and d.get("toolDenialKind") and isinstance(m.get("content"), list):
            for b in m["content"]:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    name, path = tools.get(b.get("tool_use_id"), (None, None))
                    could = [h for h in hooks if h["event"] == "PreToolUse"
                             and re.fullmatch(h.get("matcher") or ".*", name or "")]
                    rows.append({"time": ts, "hook": str(could[0]["hook"]) if len(could) == 1 else "?",
                                 "event": "PreToolUse", "tool": name, "file": path, "verdict": "deny",
                                 "problem": text_of(b.get("content")), "kind": d["toolDenialKind"]})
    return rows


CHECK_EVENTS = {"PreToolUse", "PostToolUse", "PostToolUseFailure", "Stop", "SubagentStop", "UserPromptSubmit",
                "PermissionRequest"}
CRASH = re.compile(r"[Ss]yntax ?[Ee]rror|Traceback \(most recent|command not found|: not found|No such file|"
                   r"Permission denied|unexpected EOF|cannot execute|ModuleNotFoundError")


def hook_status(s1: dict | None, turns: list[dict], rule_ids: list[str]) -> dict:
    """B and C: whether each policy rule had a working hook in the task. A hook works when it runs at an event that can
    check or stop the work, never fails to run, never exits with an error that Claude Code does not pass to the agent
    (exit 1), and never passes a turn in which MTAC's check failed the rule. A hook that never had to stop the agent
    counts as working: the run cannot show otherwise. {rule: {"working", "stops" (blocks and denials), "why"}}.
    Each installed hook also gets its own "status" and "said" (its first message that stopped the agent)."""
    if not s1:
        return {}
    out = {}
    for rid in rule_ids + [None]:                                  # None: hooks whose rule was not found
        hooks, reasons, working, stops = [h for h in s1["install"]["hooks"] if h["rule"] == rid], [], False, 0
        for hk in hooks:
            n, why = str(hk["n"]), []
            per = [t["by_hook"].get(n, {}) for t in turns]
            ran = sum(sum(v for k, v in c.items() if k not in ("sample", "said")) for c in per)
            hk["said"] = next((c["said"] for c in per if c.get("said")), None)
            if hk["event"] not in CHECK_EVENTS:
                why.append("only changes what is displayed, not the recorded reply" if hk["event"] == "MessageDisplay"
                           else f"runs at {hk['event']}, which cannot check the work")
                reasons += [f"hook {n} ({hk['event']}): {w}" for w in why]
                hk["status"] = {"working": False, "short": "display only" if hk["event"] == "MessageDisplay"
                                else "cannot check the work", "why": why[0], "stops": 0}
                continue
            if not ran:
                why.append("never ran in the task")
            crash = sum(c.get("crash", 0) for c in per)
            if crash:
                sample = next(c["sample"] for c in per if c.get("sample"))
                why.append(f"fails to run ({crash}×: {sample.strip().splitlines()[0][:90]})")
            if sum(c.get("error", 0) for c in per):
                why.append("exits 1, so Claude Code does not tell the agent")
            missed = [k + 1 for k, (t, c) in enumerate(zip(turns, per))
                      if rid and any(sc["rule"] == rid and sc["passed"] is False for sc in t["scores"])
                      and c.get("pass") and not any(c.get(v) for v in ("block", "deny", "gave up", "crash"))]
            if missed:
                why.append(f"passed turn {', '.join(map(str, missed))}, where MTAC's check failed")
            working |= not why
            reasons += [f"hook {n} ({hk['event']}): {w}" for w in why]
            own = sum(c.get(v, 0) for c in per for v in ("block", "deny", "gave up"))
            stops += own
            bad = [x for x, on in (("never ran", not ran), ("fails to run", crash),
                                   ("exit 1: agent not told", any(w.startswith("exits 1") for w in why)),
                                   ("missed a violation", missed)) if on]
            hk["status"] = {"working": not why, "stops": own, "why": "; ".join(why),
                            "short": ", ".join(([f"stopped the agent {own}×"] if own else []) + bad)
                            or "never had to stop the agent"}
        if rid is None:
            continue
        out[rid] = {"working": working, "stops": stops,
                    "why": "; ".join(reasons) if hooks else "no hook was built for this rule"}
    return out


MSG = re.compile(r"""(?:echo|printf|print|exit|die|fail|reason|Reason|additionalContext|systemMessage)["']?\s*[:=(]?\s*(?:-[en]\s+)?f?(["'])((?:(?!\1)[^\n]){10,}?)\1""")
HEREDOC_BODY = re.compile(r"(?:cat|tee)\s+(?:-a\s+)?>{0,2}\s*['\"]?([/\w.\-]+)['\"]?\s*<<-?\s*['\"]?(\w+)['\"]?\n(.*?)\n\2\b", re.S)
CHECKS = {"Stop": ("checks each reply", "blocks it"), "SubagentStop": ("checks each subagent reply", "blocks it"),
          "PreToolUse": ("checks each {m} before it runs", "denies it"), "PostToolUse": ("checks each {m} after it runs", None),
          "PostToolUseFailure": ("checks each failed {m}", None), "UserPromptSubmit": ("checks each user prompt", "blocks it"),
          "PermissionRequest": ("checks each permission request for {m}", "denies it")}


def written_files(lines: list[dict]) -> dict[str, str]:
    """The last content phase 0 wrote to each path: Write calls and shell heredocs (`cat > path << EOF`)."""
    out = {}
    for d in lines:
        m = d.get("message") or {}
        if d.get("type") != "assistant" or not isinstance(m.get("content"), list):
            continue
        for b in m["content"]:
            if not isinstance(b, dict) or b.get("type") != "tool_use":
                continue
            inp = b.get("input") or {}
            if b.get("name") == "Write" and inp.get("file_path"):
                out[inp["file_path"]] = inp.get("content", "")
            elif b.get("name") == "Bash":
                for path, _, body in HEREDOC_BODY.findall(inp.get("command", "")):
                    out[path] = body
    return out


def hook_says(cmd: str, contents: dict[str, str]) -> str | None:
    """What a hook tells the agent, read from its command and its scripts: the first message it prints, exits with or
    gives as a reason. None when no such text is found."""
    texts = [cmd] + [contents.get(p, "") for p in re.findall(r"/opt/[\w./-]+\.\w+", cmd)]
    lines = [ln for t in texts for ln in t.splitlines()]
    for strict in (True, False):                        # first the lines that write to stderr or give a reason
        for ln in lines:
            if strict and not re.search(r">&2|stderr|reason|Reason|exit|additionalContext", ln):
                continue
            for m in MSG.finditer(ln):
                s = m.group(2).strip()
                if (" " in s or re.search(r"[一-鿿]", s)) and not re.match(r"[.$/{\[]|jq |grep ", s):
                    return re.sub(r"\$\{?\w+\}?|\{[\w.\[\]'\"()]+\}", "…", s.replace('\\"', '"'))
    return None


def hook_line(hk: dict) -> str:
    """One hook as one short line: what it checks, what it does when the check fails, and the message it then sends
    to the agent (or its script, when no message was found)."""
    ev, parts = hk["event"], [x.strip() for x in re.split(r"[|,]", hk.get("matcher") or "") if x.strip()]
    m = "Write/Edit" if parts and set(parts) <= {"Write", "Edit", "MultiEdit", "NotebookEdit"} else "/".join(parts) or "tool call"
    said = hk.get("says") or hk.get("said")
    script = next(iter(re.findall(r"/opt/[\w./-]+\.\w+", hk["command"])), None)
    msg = f"“{first_line(said, 110)}”" if said else None
    where = f" (script: {Path(script).name})" if script else ""
    head = f"Claude Code hook, {hk.get('rule') or 'rule not found'}: "
    if ev == "MessageDisplay":
        return head + "rewrites the text shown on screen, not the reply that is recorded" + where
    if ev == "SessionStart":
        return head + "at session start, adds text to the agent's context" + (f": {msg}" if msg else where)
    check, act = CHECKS.get(ev, (f"runs at {ev}", None))
    check = check.format(m=m)
    if msg:
        return head + f"{check}; if the check fails, {act + ' and ' if act else ''}tells the agent {msg}"
    return head + f"{check}; if the check fails, {act or 'tells the agent'}{where}"


def first_line(s: str, n: int) -> str:
    s = str(s).strip().splitlines()[0] if str(s).strip() else ""
    return s if len(s) <= n else s[:n] + "…"


def phase0_extras(files: dict, env: dict, install: dict, ws: dict, written: dict, hooks_text: str) -> list[str]:
    """What phase 0 implemented besides the hooks, read from the container after it: tools installed (and whether a
    hook uses them), commands made available to `agent`, scripts and configs written, changes in /workspace, other
    Claude Code settings and system changes. Notes and reports it wrote are left out."""
    out, tops = [], {}
    for k in files:
        if "/" in k:
            tops.setdefault(k.split("/")[0], []).append(k)
    unused = lambda *names: "" if any(n and n.lower() in hooks_text.lower() for n in names) else " (no hook uses it)"
    for d, ks in sorted(tops.items()):
        dists = sorted({re.sub(r"\.dist-info$", "", p) for k in ks for p in k.split("/") if p.endswith(".dist-info")})
        mods = sorted({k.split("node_modules/")[1].split("/")[0] for k in ks if "node_modules/" in k})
        if d.startswith("node-v"):
            out.append(f"Installed Node.js {d.split('-')[1]} in /opt/enforce/{d}" + unused(d))
        elif d.startswith("jdk"):
            out.append(f"Installed Java ({d}) in /opt/enforce/{d}" + unused(d))
        elif dists:
            main = [x for x in dists if x.split("-")[0].lower() in d.lower()] or dists[:1]
            out.append(f"Installed {', '.join(main)} in a Python environment, /opt/enforce/{d}"
                       + unused(d, *(m.split("-")[0] for m in main)))
        elif mods:
            out.append(f"Installed npm packages in /opt/enforce/{d}: {', '.join(mods[:6])}"
                       + (f" and {len(mods) - 6} more" if len(mods) > 6 else "") + unused(d, *mods[:6]))
    if env.get("packages_added"):
        out.append("Installed system packages: " + ", ".join(map(str, env["packages_added"][:8])))
    if install.get("commands_added_for_agent"):
        out.append("Made these commands available to the user agent: " + ", ".join(install["commands_added_for_agent"]))
    kinds = {"script": (".sh", ".py", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl"), "config": (".json", ".yml", ".yaml", ".toml", ".ini", ".cfg")}
    def wrote(paths: list[str], where: str) -> None:
        parts = []
        for kind, ext in kinds.items():
            names = [Path(x).name for x in paths if x.endswith(ext)]
            if names:
                parts.append(f"{len(names)} {kind}{'s' * (len(names) != 1)} ({', '.join(names[:4])}{', …' if len(names) > 4 else ''})")
        if parts:
            out.append(f"Wrote {' and '.join(parts)} in {where}")
    wrote([k for k in files if not (set(Path(k).parts[:-1]) & TOOL_DIRS) and not k.split("/")[0].startswith(("node-v", "jdk"))
           and not any(k.startswith(d + "/") for d, ks in tops.items() if len(ks) > 20)], "/opt/enforce")
    away: dict[str, list[str]] = {}
    for path in written:                               # files phase 0 wrote outside /opt/enforce, by folder
        if not path.startswith(("/opt/enforce/", "/tmp/", "/workspace/")):
            away.setdefault(str(Path(path).parent), []).append(path)
    for folder, paths in sorted(away.items()):
        wrote(paths, folder)
    made = {k: v for k, v in ws.items() if isinstance(v, (list, dict)) and v}
    if made:
        out.append("Changed /workspace: " + "; ".join(f"{k} {', '.join(sorted(v)[:4])}" for k, v in made.items()))
    other = [k for k in (install.get("install") or {}).get("other_settings") or [] if k != "$schema"]
    if other:
        out.append("Set other Claude Code settings: " + ", ".join(other))
    if (install.get("install") or {}).get("not_wrapped"):
        out.append(f"Added {len(install['install']['not_wrapped'])} hooks that are not commands")
    for key, label in (("git_system_config", "Set a system git config"), ("crontabs", "Added cron jobs"),
                       ("users_added", "Added users"), ("processes_started", "Left processes running")):
        if env.get(key):
            v = env[key]
            out.append(f"{label}: " + (", ".join(map(str, v[:5])) if isinstance(v, list) else str(v)[:120]))
    return out


def phase0_summary(s1: dict | None) -> list[str]:
    """What the phase 0 agent implemented, in short items: one per hook (in rule order), then the rest."""
    if not s1:
        return []
    order = {r["rule"]: i for i, r in enumerate(s1["rules"])}
    hooks = sorted(s1["install"]["hooks"], key=lambda h: (order.get(h.get("rule"), 99), int(h["n"])))
    return [hook_line(h) for h in hooks] + s1["extras"]


TOOL_DIRS = {"node_modules", "site-packages", "dist-packages", "lib", "lib64", "include", "share", "bin", "__pycache__",
             ".cache", "venv", ".venv", "semgrep-venv", "jsonschema-venv"}


def own_files(files: dict) -> dict:
    """The files phase 0 wrote in /opt/enforce (scripts, configs, notes); installed tools and binaries are counted only."""
    own, skipped = {}, 0
    for path, content in sorted(files.items()):
        parts = set(Path(path).parts[:-1])
        if parts & TOOL_DIRS or any(x.startswith("node-v") or x.startswith("jdk") for x in parts) \
                or content in ("(binary)",) or str(content).startswith("(") and str(content).endswith(" bytes)") or len(own) >= 150:
            skipped += 1
            continue
        own[path] = cut(content, 6000)
    return {"enforce_files": own, "enforce_files_skipped": skipped}


def violations(run: Path, q: MTACIFBenchQuestion, rule_of: dict, replies: dict) -> dict:
    """Where MTAC's checker failed each failed policy item of each turn, found black-box (mtac_locate.py: the
    checker run again on reduced copies of the reply and the workspace; its code stays unread). Cached in
    <run>/violations.json until the run is scored again. {"<round>|<rule>": rows or None}."""
    cache, scores = run / "violations.json", run / "script_scores.json"
    if not scores.exists():
        return {}
    if cache.exists() and cache.stat().st_mtime >= scores.stat().st_mtime:
        return json.loads(cache.read_text(encoding="utf-8"))
    raw = next(t for t in map(json.loads, MTAC.read_text(encoding="utf-8").splitlines()) if t["task_id"] == q.task_id)
    code = {(str(rnd["round_id"]), c["constraint"].strip()): c["validation_code"] for rnd in raw["rounds"]
            for c in rnd["instruction_following_checklist"] if c["validation_code"].strip()}
    leave_out = score_runs.phase0_files(run, q.workspace_dir)
    jobs = []
    for rnd in json.loads(scores.read_text(encoding="utf-8"))["rounds"]:
        for item in rnd["items"]:
            rule = rule_of.get(item["requirement"].strip())
            if rule and item["passed"] is False:
                jobs.append((str(rnd["round_id"]), rule, item["requirement"].strip()))

    def one(job):
        rid, rule, req = job
        mat = run / "turns" / f"round_{rid}"
        files = {k: v for k, v in mtac_locate.text_files(mat / "workspace_snapshot").items() if k not in leave_out}
        reply = replies.get(rid) or (mat / "last_response.txt").read_text(encoding="utf-8", errors="ignore")
        try:
            return f"{rid}|{rule}", mtac_locate.locate(mtac_locate.Checker(code[(rid, req)], q.validation_code_timeout),
                                                       req, reply, files)
        except Exception:
            return f"{rid}|{rule}", None

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(8) as pool:
        out = dict(pool.map(one, jobs))
    cache.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {run.relative_to(EXP)}: {len(jobs)} failed policy items located "
          f"({sum(1 for v in out.values() if v)} with a place)")
    return out


def task_part(run: Path, q: MTACIFBenchQuestion, rule_of: dict, hooks: list[dict] | None = None) -> dict:
    traces = [t for t in (run / "traces").glob("*.jsonl")
              if not t.name.endswith(".enforce.jsonl") and not t.name.endswith(".fingerprint.txt")]
    lines = lines_of(traces[0]) if traces else []
    enforce = next(iter((run / "traces").glob("*.enforce.jsonl")), None)
    log = lines_of(enforce) if enforce else transcript_rows(lines, hooks or [])   # point 81: the transcript
    replies = score_runs.turn_replies(run, q)
    located = violations(run, q, rule_of, replies)
    scores = json.loads((run / "script_scores.json").read_text(encoding="utf-8")) if (run / "script_scores.json").exists() else {"rounds": []}
    by_round = {str(r["round_id"]): r for r in scores["rounds"]}
    starts = [i for i, d in enumerate(lines) if d.get("type") == "user" and isinstance((d.get("message") or {}).get("content"), str)
              and "# 执行要求" in d["message"]["content"]]
    turns = []
    for k, rnd in enumerate(q.rounds):
        if k >= len(starts):
            break
        seg = lines[starts[k] + 1:starts[k + 1]] if k + 1 < len(starts) else lines[starts[k] + 1:]
        t0 = str(lines[starts[k]].get("timestamp", ""))[:19]
        t1 = str(lines[starts[k + 1]].get("timestamp", ""))[:19] if k + 1 < len(starts) else "9999"
        rows = [r for r in log if t0 <= str(r.get("time", "")) < t1]
        counts: dict[str, int] = {}
        by_hook: dict[str, dict] = {}
        for r in rows:
            counts[r.get("verdict", "?")] = counts.get(r.get("verdict", "?"), 0) + 1
            c, msg = by_hook.setdefault(str(r.get("hook")), {}), str(r.get("problem") or r.get("error") or "")
            kind = "crash" if r.get("verdict") != "pass" and CRASH.search(msg) else r.get("verdict", "?")
            c[kind] = c.get(kind, 0) + 1
            if kind == "crash":
                c.setdefault("sample", msg)
            elif kind in ("block", "deny", "gave up") and msg.strip():
                c.setdefault("said", msg)
        res_path = run / "turns" / f"round_{rnd.round_id}" / "result.json"
        meta = {}
        if res_path.exists():
            res = json.loads(res_path.read_text(encoding="utf-8")).get("result") or {}
            meta = {"seconds": round((res.get("duration_ms") or 0) / 1000), "model_turns": res.get("num_turns"),
                    "cost": res.get("total_cost_usd")}
        sc = by_round.get(str(rnd.round_id), {})
        turns.append({"round": rnd.round_id, "request": rnd.prompt, "t": hms(lines[starts[k]]),
                      "prompt": lines[starts[k]]["message"]["content"], "events": events(seg, 1),
                      "reply": replies.get(str(rnd.round_id), ""), "verdicts": counts, "by_hook": by_hook,
                      "blocks": [{"hook": r.get("hook"), "event": r.get("event"), "verdict": r.get("verdict"),
                                  "file": r.get("file"), "msg": cut(r.get("problem") or r.get("error") or "", 600)}
                                 for r in rows if r.get("verdict") != "pass"][:60],
                      "scores": [{"rule": rule_of.get(i["requirement"].strip()), "req": i["requirement"],
                                  "passed": i["passed"]} for i in sc.get("items", [])],
                      "fails": {key.split("|")[1]: rows for key, rows in located.items()
                                if key.split("|")[0] == str(rnd.round_id)}, **meta})
    return {"turns": turns, "t0": hms(lines[starts[0]]) if starts else ""}


def cost(label: str) -> list[float]:
    s1 = task = 0.0
    for r in paths.ledger_rows():
        run = r.get("run") or ""
        if run == f"{label}/translation":
            s1 += r.get("cost") or 0
        elif run == label:
            task += r.get("cost") or 0
    return [round(s1, 2), round(task, 2)]


def load(run: Path) -> dict:
    info = paths.run_info(run)
    arm, tid = info["arm"], info["task"]
    q = MTACIFBenchQuestion.model_validate(json.loads(
        (paths.task_dir(tid) / "data" / "questions.jsonl").read_text(encoding="utf-8").splitlines()[0]))
    rules = json.loads((paths.task_dir(tid) / "rules.json").read_text(encoding="utf-8"))
    rule_of = {r["constraint"].strip(): f"R{r['item']}" for r in rules}
    inputs = json.loads((run / "inputs.json").read_text(encoding="utf-8"))
    s1 = phase0(run, arm, tid)
    hooks = installed_hooks(json.loads((run / "phase0" / "install.json").read_text(encoding="utf-8"))) \
        if (run / "phase0" / "install.json").exists() else []
    tp = task_part(run, q, rule_of, hooks)
    status = hook_status(s1, tp["turns"], [f"R{r['item']}" for r in rules])   # also gives each hook its status
    if s1:
        s1["summary"] = phase0_summary(s1)
    return {"task": tid, "arm": ARM_NAME[arm], "run": inputs["run"], "image": inputs["image"],
            "claude_code": inputs["claude_code"], "model": inputs["model"], "flags": inputs["flags"],
            "note": inputs["task_note"], "policy": q.repository_policy.strip(),
            "rules": [{"id": f"R{r['item']}", "text": r["constraint"], "scored": r["scored"]} for r in rules],
            "cost": cost(inputs["run"]), "phase0": s1, "task_part": tp,
            "hook_status": status}


def main(argv: list[str]) -> None:
    runs = [Path(a).resolve() for a in argv] or paths.latest_runs(paths.DEFAULT_AGENT, (46, 91), ("A", "B", "C"))
    data = [load(r) for r in runs]
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", blob), encoding="utf-8")
    print(f"{OUT.relative_to(EXP)}: {len(data)} runs, {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main(sys.argv[1:])
