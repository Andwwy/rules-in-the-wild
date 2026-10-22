"""R7: 生成的代码文件必须满足：单个函数的规模不得大于 60 行 (no function in a code file is longer than 60 lines).
Semgrep finds every function and method (/opt/enforce-toolbox/skeletons/semgrep_check.py); judge() computes the
length, which Semgrep cannot: from the line of its signature to the line where it ends, both counted. Code in HTML,
Vue and Svelte files is taken out of its <script> blocks first, at the same line numbers. Shell functions, which
Semgrep 1.177 cannot match (no Bash pattern for a function definition parses or matches), are found by their braces.
R7_function_length.py FILE ...
"""
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, "/opt/enforce")
from common import read                                         # noqa: E402

SEMGREP = "/opt/enforce/tool-installs/bin/semgrep"
MAX_LINES = 60
RULES = """rules:
- id: function
  languages: [javascript, typescript]
  severity: ERROR
  message: a function
  pattern-either:
  - pattern: function $F(...) { ... }
  - pattern: function (...) { ... }
  - pattern: (...) => $BODY
- id: function-py
  languages: [python]
  severity: ERROR
  message: a function
  pattern: |
    def $F(...):
        ...
"""
SCANNED = {".js": ".js", ".mjs": ".js", ".cjs": ".js", ".jsx": ".jsx", ".ts": ".ts", ".mts": ".ts", ".cts": ".ts",
           ".tsx": ".tsx", ".py": ".py", ".pyw": ".py"}
CONTAINERS = (".html", ".htm", ".xhtml", ".vue", ".svelte")
SHELL = (".sh", ".bash", ".zsh")
SHELL_FUNCTION = re.compile(r"^\s*(?:function\s+[\w:.-]+\s*(?:\(\s*\))?|[\w:.-]+\s*\(\s*\))\s*\{?\s*(?:#.*)?$")
SCRIPT = re.compile(r"(<script\b([^>]*)>)(.*?)</script\s*>", re.S | re.I)


def scripts(text: str) -> tuple[str, str] | None:
    """The code of the <script> blocks without src, at its own line numbers (everything else blank), and its kind."""
    out, kind, last = [], ".js", 0
    for m in SCRIPT.finditer(text):
        if re.search(r"\bsrc\s*=", m.group(2)):
            continue
        if re.search(r"""lang\s*=\s*["']?ts""", m.group(2)):
            kind = ".ts"
        start = m.start(3)
        out.append(re.sub(r"[^\n]", " ", text[last:start]))         # keep the line numbers
        out.append(m.group(3))
        last = m.end(3)
    return ("".join(out), kind) if out else None


def shell_functions(text: str) -> list[dict]:
    """Shell functions as Semgrep's matches: {"start": {"line"}, "end": {"line"}}, by their braces."""
    lines, out = text.split("\n"), []
    for k, line in enumerate(lines):
        if not SHELL_FUNCTION.match(line):
            continue
        depth, opened = 0, False
        for j in range(k, len(lines)):
            code = re.sub(r"#.*$|'[^']*'|\"(?:[^\"\\]|\\.)*\"", "", lines[j])
            depth += code.count("{") - code.count("}")
            opened = opened or "{" in code
            if opened and depth <= 0:
                out.append({"start": {"line": k + 1}, "end": {"line": j + 1}})
                break
    return out


def judge(match: dict, where: str, lines: list[str]) -> str | None:
    start, end = match["start"]["line"], match["end"]["line"]
    n = end - start + 1
    if n <= MAX_LINES:
        return None
    head = lines[start - 1].strip()[:70] if start <= len(lines) else ""
    return (f"R7 {where}:{start}: this function is {n} lines (lines {start} to {end}): '{head}'; no function may be "
            f"longer than {MAX_LINES} lines: split it into smaller functions")


def check(items: list[tuple[str, str]]) -> list[str]:
    """items: (where, content) of code files -> the violations. Each is scanned as a copy with a neutral name, so that
    Semgrep's own ignore lists (tests/, *.min.js, ...) skip nothing."""
    found = []
    with tempfile.TemporaryDirectory() as d:
        todo = {}
        for k, (where, content) in enumerate(items):
            ext = os.path.splitext(where)[1].lower()
            if ext in SHELL:
                lines = content.split("\n")
                found += [v for m in shell_functions(content) if (v := judge(m, where, lines))]
                continue
            if ext in CONTAINERS:
                got = scripts(content)
                if not got:
                    continue
                content, kind = got
            elif ext in SCANNED:
                kind = SCANNED[ext]
            else:
                continue
            name = os.path.join(d, f"f{k:05d}{kind}")
            with open(name, "w", encoding="utf-8") as f:
                f.write(content)
            todo[name] = (where, content.split("\n"))
        if not todo:
            return found
        cfg = os.path.join(d, "rules.yml")
        with open(cfg, "w", encoding="utf-8") as f:
            f.write(RULES)
        done = subprocess.run([SEMGREP, "scan", "--config", cfg, "--json", "--metrics=off", "--quiet",
                               "--disable-version-check", *todo], capture_output=True, text=True, cwd=d)
        try:
            results = json.loads(done.stdout)["results"]
        except (ValueError, KeyError):
            raise RuntimeError(f"semgrep failed (exit {done.returncode}): {(done.stderr or done.stdout)[-600:]}")
        for m in sorted(results, key=lambda m: (m["path"], m["start"]["line"])):
            path = m["path"] if os.path.isabs(m["path"]) else os.path.join(d, m["path"])
            where, lines = todo[os.path.normpath(path)]
            v = judge(m, where, lines)
            if v and v not in found:
                found.append(v)
        return found


if __name__ == "__main__":
    found = check([(f, read(f)) for f in sys.argv[1:]])
    print("\n".join(found), file=sys.stderr)
    sys.exit(1 if found else 0)
