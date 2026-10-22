#!/usr/bin/env python3
"""<rule id>: <the rule>, with Semgrep finding the code.   semgrep_check.py FILE ...
Semgrep matches syntax (the rules below); judge() decides what breaks the rule, so a value Semgrep cannot compute (a
length, a count) is computed here from each match. Exit 0: the files follow the rule. Exit 1: each violation (where,
and what to change). Semgrep is called by its full path: a hook runs with the agent's PATH."""
import json, os, subprocess, sys, tempfile

SEMGREP = "/opt/enforce/tool-installs/bin/semgrep"
RULES = """rules:
- id: <id>
  languages: [<language>]
  severity: ERROR
  message: <what Semgrep finds>
  pattern: <code pattern>
"""

def judge(match: dict, path: str) -> str | None:
    """A match ({"check_id", "start": {"line"}, "end": {"line"}, "extra": {"lines"}}) -> the violation, or None."""
    # <the rule>, for example a length: lines = match["end"]["line"] - match["start"]["line"] + 1
    return f"{path}:{match['start']['line']}: <what breaks the rule>; <what to change>"

cfg = tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False)
cfg.write(RULES); cfg.close()
found = []
for path in sys.argv[1:]:
    done = subprocess.run([SEMGREP, "scan", "--config", cfg.name, "--json", "--metrics=off", "--quiet", path],
                          capture_output=True, text=True)
    for m in json.loads(done.stdout or "{}").get("results", []):
        v = judge(m, path)
        if v:
            found.append(v)
os.unlink(cfg.name)
print("\n".join(found), file=sys.stderr)
sys.exit(1 if found else 0)
