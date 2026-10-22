"""What phase 0 (the translation) changed in the agent's container, outside /workspace (arms B and C; design_process.md,
point 39). Copied into the container as /opt/enforce-harness/environment.py; uses only python3's standard library.

    python3 environment.py --before     before phase 0: a time marker and the state that files do not show
    python3 environment.py --after      after phase 0: prints the changes as JSON, and writes the changed files
                                        outside /opt/enforce to /opt/enforce-harness/watched.txt (the fingerprint then
                                        covers them, to see whether the task's agent changes them)
    python3 environment.py --settings   the agent's Claude Code settings files that exist (every scope it loads in
                                        /workspace) and their hooks, numbered in that order (JSON)
    python3 environment.py --fingerprint   a hash of the enforcement: those settings files, /opt/enforce and the other
                                        files that phase 0 changed (checked again after each task turn)

Changes: files created or changed (by folder, and each file outside /opt/enforce with its size), Debian packages added,
users added, processes started that still run, git's system config, crontabs. Not recorded here: /workspace
(scripts/runner.py records it file by file, and keeps it), /root/.claude and /root/.claude.json (phase 0's own),
the harness, the sandbox's own files, caches, and /var/lib/enforce-state (the enforcement's state: it changes while the
task runs, so the fingerprint must not cover it; design_process.md, point 73).

The harness installs nothing: phase 0 writes the agent's settings where Claude Code looks for them, and the agent
loads them as they are (design_process.md, point 81). --settings only lists them, for the record and for reading the
hooks' outcomes in the agent's transcript.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

HARNESS = "/opt/enforce-harness"
MARKER, BEFORE, WATCHED = f"{HARNESS}/start.marker", f"{HARNESS}/before.json", f"{HARNESS}/watched.txt"
PRUNE = ("/proc", "/sys", "/dev", "/run", "/workspace", "/root/.claude", "/root/.cache", "/root/.npm", HARNESS,
         "/tmp/offline_package", "/var/lib/enforce-state",
         "/var/cache", "/var/lib/apt", "/var/lib/dpkg", "/var/log")      # /var/lib/enforce-state: the enforcement's
                                                                          # own state, which changes during the task
MAX_LISTED = 500
ENFORCE = "/opt/enforce"
# Every settings file the agent's Claude Code loads when it runs as `agent` in /workspace, by scope (highest first)
SETTINGS = [("managed", "/etc/claude-code/managed-settings.json"), ("managed", "/etc/claude-code/managed-settings.d"),
            ("project local", "/workspace/.claude/settings.local.json"), ("project", "/workspace/.claude/settings.json"),
            ("user", "/home/agent/.claude/settings.json")]
SKIP = {"node_modules", ".git", "__pycache__", "tool-installs", "venv", ".venv", ".cache"}
# Not the translation's: AgentProbe's prompt files, the sandbox's command output files, Claude Code's own state file
NOISE = re.compile(r"/tmp/prompt_\w+\.txt|/tmp/[0-9a-f]{32}\.(stdout|stderr)|/root/\.claude\.json(\.backup)?")


def sh(cmd: str) -> str:
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return ""


def state() -> dict:
    return {"packages": sorted(sh("dpkg-query -W -f='${Package}\\n'").split()),
            "users": sorted(line.split(":")[0] for line in sh("getent passwd").splitlines() if line),
            "processes": sorted({a for a in sh("ps -eo args=").splitlines()
                                 if "environment.py" not in a and not a.startswith("ps ")}),
            "git_system_config": sh("git config --system --list 2>/dev/null"),
            "crontabs": sh("ls /var/spool/cron/crontabs 2>/dev/null; cat /etc/crontab 2>/dev/null")}


def changed_files() -> list[str]:
    since = os.path.getmtime(MARKER)
    out = []
    for root, dirs, files in os.walk("/", topdown=True):
        dirs[:] = [d for d in dirs if not os.path.join(root, d).startswith(PRUNE)
                   and not os.path.islink(os.path.join(root, d))]
        for f in files:
            p = os.path.join(root, f)
            try:
                if os.lstat(p).st_mtime >= since and not NOISE.fullmatch(p):
                    out.append(p)
            except OSError:
                pass
    return sorted(out)


def settings_files() -> list[tuple[str, str]]:
    out = []
    for scope, path in SETTINGS:
        if os.path.isdir(path):
            out += [(scope, os.path.join(path, f)) for f in sorted(os.listdir(path)) if f.endswith(".json")]
        elif os.path.isfile(path):
            out.append((scope, path))
    return out


def settings() -> dict:
    """The agent's settings files, the hooks in them as Claude Code's documented schema reads them (an event's list of
    matcher groups, each with its own list `hooks`), and the entries that do not have that form: Claude Code drops
    those without a word in `claude -p`, and a broken entry can drop the file's whole `hooks` field."""
    files, hooks, malformed = [], [], []
    for scope, path in settings_files():
        try:
            data = json.load(open(path, encoding="utf-8"))
            assert isinstance(data, dict)
        except Exception as err:
            files.append({"scope": scope, "path": path, "error": f"{type(err).__name__}: {err}"})
            continue
        files.append({"scope": scope, "path": path, "keys": sorted(data)})
        for event, entries in (data.get("hooks") or {}).items():
            if not isinstance(entries, list):
                malformed.append({"scope": scope, "path": path, "event": event, "entry": entries,
                                  "problem": "the event's value is not a list of matcher groups"})
                continue
            for entry in entries:
                if not (isinstance(entry, dict) and isinstance(entry.get("hooks"), list)):
                    malformed.append({"scope": scope, "path": path, "event": event, "entry": entry,
                                      "problem": "a matcher group without its list `hooks`"})
                    continue
                for h in entry["hooks"]:
                    hooks.append({"hook": len(hooks) + 1, "scope": scope, "event": event, "matcher": entry.get("matcher"),
                                  "type": h.get("type", "command"), "command": h.get("command"),
                                  **({"args": h["args"]} if isinstance(h.get("args"), list) else {})})
    return {"files": files, "hooks": hooks, "malformed": malformed}


def fingerprint() -> str:
    """sha256 over the agent's settings files, the enforcement's own files (big tool folders skipped) and the other
    files that phase 0 changed (watched.txt)."""
    h = hashlib.sha256()
    try:
        watched = [p for p in open(WATCHED, encoding="utf-8").read().splitlines() if p]
    except OSError:
        watched = []
    for root in (*[p for _, p in settings_files()], ENFORCE, *watched):
        paths = [root] if os.path.isfile(root) else sorted(
            os.path.join(d, f) for d, dirs, files in os.walk(root) for f in files
            if not SKIP & set(os.path.relpath(d, root).split(os.sep)))
        for p in paths:
            try:
                if os.path.getsize(p) <= 2_000_000:
                    h.update(p.encode()); h.update(open(p, "rb").read())
            except OSError:
                pass
    return h.hexdigest()


def main(arg: str) -> int:
    if arg == "--settings":
        print(json.dumps(settings(), ensure_ascii=False))
        return 0
    if arg == "--fingerprint":
        print(fingerprint())
        return 0
    if arg == "--before":
        os.makedirs(HARNESS, exist_ok=True)
        open(MARKER, "w").close()
        json.dump(state(), open(BEFORE, "w"))
        return 0
    before, after, files = json.load(open(BEFORE)), state(), changed_files()
    by_folder: dict[str, int] = {}
    for p in files:
        top = "/".join(p.split("/")[:3]) if not p.startswith("/opt/enforce/") else "/opt/enforce"
        by_folder[top] = by_folder.get(top, 0) + 1
    outside = [p for p in files if not p.startswith("/opt/enforce/")]
    with open(WATCHED, "w") as f:
        f.write("\n".join(outside[:2000]) + ("\n" if outside else ""))
    report = {
        "files_total": len(files), "by_folder": dict(sorted(by_folder.items())),
        "outside_opt_enforce": [{"path": p, "size": os.path.getsize(p) if os.path.isfile(p) else None,
                                 "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest()
                                 if os.path.isfile(p) and os.path.getsize(p) <= 2_000_000 else None}
                                for p in outside[:MAX_LISTED]],
        "outside_listed": min(len(outside), MAX_LISTED), "outside_total": len(outside),
        "packages_added": sorted(set(after["packages"]) - set(before["packages"])),
        "users_added": sorted(set(after["users"]) - set(before["users"])),
        "processes_started": sorted(set(after["processes"]) - set(before["processes"])),
        "git_system_config": after["git_system_config"] if after["git_system_config"] != before["git_system_config"] else None,
        "crontabs": after["crontabs"] if after["crontabs"] != before["crontabs"] else None,
    }
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "--after"))
