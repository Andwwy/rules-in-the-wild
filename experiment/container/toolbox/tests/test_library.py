"""The toolbox's tests, in MTAC's image as root (tests/in_image.sh): every recipe installs; the command that an enforcer
node gives for each recipe flags a bad file and passes a good one; every skeleton in skeletons/ works as published (the
check script, the regular expressions, the project and JSON Schema checks, the Rego policy and its gate, the Dogwood
policy, schema and gate, a command wrapper and a git hook as the user agent, a file watcher, file permissions, the
parsers for names in code); every link of graph.json resolves. Examples are neutral: no task's rules. Prints one line
per test and exits 1 if any fails."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

LIB = Path(__file__).resolve().parent.parent
BIN = "/opt/enforce/tool-installs/bin"
ENV = {**os.environ, "PATH": f"{BIN}:{os.environ['PATH']}"}
RESULTS: list[tuple[bool, str]] = []


def ok(cond: bool, name: str, detail: str = "") -> None:
    RESULTS.append((cond, name))
    print(f"{'✓' if cond else '✗'} {name}" + ("" if cond else f": {detail[-400:]}"), flush=True)


def run(cmd, user: str | None = None, **kw) -> subprocess.CompletedProcess:
    if user:
        cmd = ["runuser", "-u", user, "--", "env", f"PATH={ENV['PATH']}", "HOME=/home/agent", *cmd]
    return subprocess.run(cmd, capture_output=True, text=True, env=ENV, **kw)


# ---- recipes, and the command that each enforcer node gives for them ---------------------------------------------------
# (recipe, command, file name, bad content, good content, stdin): the command as the enforcer node gives it, filled in
WORK = Path(tempfile.mkdtemp(prefix="lib-"))
CFG = WORK / "cfg"
CFG.mkdir()
(CFG / "eslint.config.mjs").write_text('export default [{ rules: { "no-var": "error" } }];\n')
(CFG / "stylelintrc.json").write_text('{"rules": {"color-no-invalid-hex": true}}\n')
(CFG / "vale.ini").write_text("[*.md]\nVale.Repetition = YES\n")
(CFG / "markdownlint-cli2.jsonc").write_text('{"config": {"default": false, "MD001": true}}\n')
(CFG / "schema.json").write_text('{"type": "object", "required": ["name"]}\n')
(CFG / "rules.yml").write_text("rules:\n  - id: no-eval\n    languages: [python]\n    severity: ERROR\n"
                               "    message: do not call eval\n    pattern: eval(...)\n")
RM = "/opt/enforce/tool-installs/remark-lint/node_modules"
CL = "/opt/enforce/tool-installs/commitlint/node_modules/@commitlint/config-conventional/lib/index.js"
CASES = [
    ("eslint", ["eslint", "--config", f"{CFG}/eslint.config.mjs", "{file}"], "a.js", "var x = 1;\nconsole.log(x);\n", "let x = 1;\nconsole.log(x);\n", False),
    ("eslint", ["eslint", "--config", f"{CFG}/eslint.config.mjs", "--stdin", "--stdin-filename", "src/a.js"], "a.js", "var x = 1;\nconsole.log(x);\n", "let x = 1;\nconsole.log(x);\n", True),
    ("stylelint", ["stylelint", "--config", f"{CFG}/stylelintrc.json", "{file}"], "s.css", "a { color: #ggg; }\n", "a { color: #fff; }\n", False),
    ("biome", ["biome", "lint", "{file}"], "b.js", "debugger;\n", "const x = 1;\nexport { x };\n", False),
    ("ruff", ["ruff", "check", "--no-cache", "--select", "E711", "{file}"], "a.py", "x = None\nif x == None:\n    pass\n", "x = None\nif x is None:\n    pass\n", False),
    ("ruff", ["ruff", "check", "--no-cache", "--select", "E711", "--stdin-filename", "a.py", "-"], "a.py", "x = None\nif x == None:\n    pass\n", "x = None\nif x is None:\n    pass\n", True),
    ("shellcheck", ["shellcheck", "--shell=bash", "--include=SC2086", "{file}"], "r.sh", "#!/bin/bash\necho $1\n", '#!/bin/bash\necho "$1"\n', False),
    ("semgrep", ["semgrep", "scan", "--config", f"{CFG}/rules.yml", "--error", "--metrics=off", "--quiet", "{file}"], "e.py", "eval(input())\n", "print(input())\n", False),
    ("vale", ["vale", "--config", f"{CFG}/vale.ini", "--output=line", "{file}"], "d.md", "This is the the end.\n", "This is the end.\n", False),
    ("markdownlint", ["markdownlint-cli2", "--config", f"{CFG}/markdownlint-cli2.jsonc", "{file}"], "h.md", "# A\n\n### B\n", "# A\n\n## B\n", False),
    ("remark-lint", ["remark", "--frail", "--quiet", "--no-stdout", "--no-config", "--use", f"{RM}/remark-preset-lint-recommended/index.js", "{file}"], "l.md", "See [docs][missing].\n", "See [docs][d].\n\n[d]: https://example.com\n", False),
    ("yamllint", ["yamllint", "-d", "{extends: default}", "{file}"], "c.yml", "---\na: 1\na: 2\n", "---\na: 1\nb: 2\n", False),
    ("commitlint", ["commitlint", "--extends", CL], "m.txt", "Bad message\n", "feat: add a check\n", True),
    ("pytest", ["pytest", "-q", "-x", "-p", "no:cacheprovider", "{dir}"], "test_a.py", "def test_a():\n    assert 1 == 2\n", "def test_a():\n    assert 1 == 1\n", False),
    ("jest", ["jest", "--config", "{}", "--rootDir", "{dir}", "--ci"], "a.test.js", 'test("a", () => { expect(1).toBe(2); });\n', 'test("a", () => { expect(1).toBe(1); });\n', False),
    ("ajv", ["ajv", "validate", "--spec=draft2020", "-s", f"{CFG}/schema.json", "-d", "{file}"], "d.json", '{"x": 1}\n', '{"name": "a"}\n', False),
    ("openapi", ["openapi-spec-validator", "{file}"], "api.yaml", "openapi: 3.0.0\ninfo: {}\npaths: {}\n", "openapi: 3.0.0\ninfo:\n  title: A\n  version: '1'\npaths: {}\n", False),
    ("typescript", ["tsc", "--noEmit", "--strict", "{file}"], "t.ts", 'let x: number = "a";\nexport { x };\n', "let x: number = 1;\nexport { x };\n", False),
    ("jq", ["jq", "-e", ".name", "{file}"], "n.json", '{"x": 1}\n', '{"name": "a"}\n', False),
]


def recipes() -> None:
    sys.path.insert(0, str(LIB))
    from enforce_lib.recipes import RECIPES
    for name in RECIPES:                                         # every recipe
        done = run([sys.executable, str(LIB / "enforce"), "install", name])
        ok(done.returncode == 0, f"recipe {name} installs", done.stdout + done.stderr)
    for recipe, cmd, fname, bad, good, stdin in CASES:
        codes = []
        for text in (bad, good):
            d = Path(tempfile.mkdtemp(prefix="case-", dir=WORK))
            f = d / fname
            f.write_text(text)
            words = [w.replace("{file}", str(f)).replace("{dir}", str(d)) for w in cmd]
            done = run(words, input=text if stdin else None, cwd=d, timeout=300)
            codes.append(done.returncode)
            out = done.stdout + done.stderr
        ok(codes[0] != 0 and codes[1] == 0, f"{recipe}: {' '.join(cmd[:3])}…{' (stdin)' if stdin else ''} flags the bad file, passes the good one",
           f"exit codes {codes}: {out}")


# ---- skeletons, as the files are published -------------------------------------------------------------------------
SK = LIB / "skeletons"


def skel(name: str) -> str:
    return (SK / name).read_text(encoding="utf-8")


def check_script() -> None:
    rule = ('    for n, line in enumerate(text.splitlines(), 1):\n        if "TODO" in line:\n'
            '            out.append(f"{where}:{n}: a TODO; finish it or remove it")\n')
    code = skel("check.py").replace(
        '    # <the rule>: out.append(f"{where}:<line>: <what breaks the rule>; <what to change>")\n', rule)
    script = WORK / "check.py"
    script.write_text(code)
    bad, good = WORK / "bad.txt", WORK / "good.txt"
    bad.write_text("a\n# TODO x\n")
    good.write_text("a\n")
    r1, r2 = run([sys.executable, str(script), str(bad)]), run([sys.executable, str(script), str(good)])
    r3 = run([sys.executable, str(script), "-"], input="TODO\n")
    ok(r1.returncode == 1 and "bad.txt:2: a TODO" in r1.stderr and r2.returncode == 0 and r3.returncode == 1,
       "skeleton check.py (file and stdin)", r1.stderr + r2.stderr)


def regexes() -> None:
    ns: dict = {}
    exec(skel("regex_validator.py").replace("<pattern>", r"\bTODO\b"), ns)
    found = ns["problems"]("a\nTODO b\n", "f.py")
    ok(found == ["f.py:2: 'TODO' breaks the rule; <what to change>"], "skeleton regex_validator.py", str(found))
    ns = {"text": "a  =  b"}
    exec(skel("regex_filter.py").replace("<pattern>", r"\s*=\s*").replace("<replacement>", " = "), ns)
    ok(ns["fixed"] == "a = b", "skeleton regex_filter.py", repr(ns.get("fixed")))
    schema = WORK / "schema.json"
    schema.write_text('{"type": "object", "required": ["name"]}')
    code = skel("json_schema.py").replace("<schema.json>", str(schema)) + \
        "\nimport sys\nsys.exit(1 if problems(sys.stdin.read(), 'd.json') else 0)\n"
    (WORK / "js.py").write_text(code)
    py = "/opt/enforce/tool-installs/jsonschema/bin/python"
    r1, r2 = run([py, str(WORK / "js.py")], input='{"x": 1}'), run([py, str(WORK / "js.py")], input='{"name": "a"}')
    ok(r1.returncode == 1 and r2.returncode == 0, "skeleton json_schema.py", r1.stderr + r2.stderr)
    proj = Path(tempfile.mkdtemp(prefix="proj-", dir=WORK))
    (proj / "big.txt").write_text("x" * 200)
    code = skel("project_check.py").replace('"/workspace"', repr(str(proj))).replace(
        "        # <the property>: out.append(f\"{path}: <what breaks the rule>; <what to change>\")",
        "        if os.path.getsize(path) > 100:\n            out.append(f\"{path}: larger than 100 bytes\")")
    ns = {}
    exec(code, ns)
    ok(len(ns["out"]) == 1 and "big.txt" in ns["out"][0], "skeleton project_check.py", str(ns.get("out")))


def tool_checks() -> None:
    """The skeletons that compose a routed tool with a check: Semgrep finds, judge() measures; pre-commit runs on one
    file outside a commit (each filled in here as phase 0 would)."""
    d = Path(tempfile.mkdtemp())
    os.chmod(d, 0o755)
    sem = skel("semgrep_check.py").replace("<id>", "fn").replace("<language>", "python").replace("<what Semgrep finds>", "a function")
    sem = sem.replace("pattern: <code pattern>", "pattern: |\n    def $F(...):\n      ...")
    sem = sem.replace("    return f\"{path}:{match['start']['line']}: <what breaks the rule>; <what to change>\"",
                      "    n = match['end']['line'] - match['start']['line'] + 1\n    return f\"{path}:{match['start']['line']}: R7 a function of {n} lines\" if n > 5 else None")
    (d / "sem.py").write_text(sem)
    (d / "big.py").write_text("def big():\n" + "".join(f"    x{i} = {i}\n" for i in range(8)))
    (d / "small.py").write_text("def small():\n    return 1\n")
    for p in d.iterdir():
        os.chmod(p, 0o755)
    bad = run(["python3", str(d / "sem.py"), str(d / "big.py")], user="agent")
    good = run(["python3", str(d / "sem.py"), str(d / "small.py")], user="agent")
    ok(bad.returncode == 1 and "R7 a function of 9 lines" in bad.stderr and good.returncode == 0,
       "skeleton semgrep_check.py, as agent", bad.stdout + bad.stderr + good.stderr)
    (d / "line.py").write_text("import sys\nbad=[f for f in sys.argv[1:] if 'coding' not in open(f).readline()]\n"
                               "[print(f'R5: {f}: no coding line') for f in bad]\nsys.exit(1 if bad else 0)\n")
    pc = skel("pre_commit_check.sh").replace("<rule id> <the rule>", "R5 coding line").replace("<rule id>", "r5")
    pc = pc.replace("<the check, run on each file it is given>", f"python3 {d}/line.py")
    (d / "pc.sh").write_text(pc)
    (d / "a.py").write_text("x = 1\n")
    (d / "b.py").write_text("# -*- coding: utf-8 -*-\nx = 1\n")
    for p in d.iterdir():
        os.chmod(p, 0o755)
    bad = run(["bash", str(d / "pc.sh"), str(d / "a.py")], user="agent")
    good = run(["bash", str(d / "pc.sh"), str(d / "b.py")], user="agent")
    ok(bad.returncode == 1 and "R5" in bad.stdout and good.returncode == 0,
       "skeleton pre_commit_check.sh, as agent", bad.stdout[-400:] + good.stdout[-200:])


def policies() -> None:
    rego = skel("policy.rego").replace("<tool>", "shell").replace(
        "<a condition on input.args>", 'contains(input.args.command, "--force")').replace(
        "<what is refused, and what to do instead>", "force is refused; push without it")
    Path("/opt/enforce").mkdir(exist_ok=True)
    Path("/opt/enforce/policy.rego").write_text(rego)
    for name, action, want in (("refuses", '{"tool": "shell", "args": {"command": "git push --force"}}', 1),
                               ("allows", '{"tool": "shell", "args": {"command": "git status"}}', 0)):
        (WORK / "action.json").write_text(action)
        (WORK / "gate.sh").write_text(skel("opa_gate.sh").replace("<action.json>", str(WORK / "action.json")))
        done = run(["bash", str(WORK / "gate.sh")])
        ok(done.returncode == want and (want == 0 or "force is refused" in done.stderr),
           f"skeletons policy.rego + opa_gate.sh {name} an action", done.stdout + done.stderr)

    d = Path("/opt/enforce/dogwood")
    d.mkdir(parents=True, exist_ok=True)
    Path("/var/lib/enforce-state").mkdir(mode=0o700, exist_ok=True)
    (d / "policy.dw").write_text(skel("policy.dw").replace("<rule id>", "push_after_green_tests"))
    (d / "schema.cedarschema").write_text(skel("schema.cedarschema"))
    v = run(["dogwood", "validate", str(d / "policy.dw"), "--policy-schema", str(d / "schema.cedarschema")])
    ok(v.returncode == 0, "skeletons policy.dw + schema.cedarschema validate", v.stdout + v.stderr)
    scope = 'scope(principal: Agent::User::"agent", resource: Agent::Workspace::"workspace")'
    caller = 'callerPrincipal: Agent::User::"agent", callerResource: Agent::Workspace::"workspace"'
    tests = lambda passed, rid: (f'{scope} Agent::Action::"RunTests"::response(input: {{ command: "pytest" }}, '
                                 f'output: {{ passed: {passed} }}, {caller}, requestId: "{rid}")')
    push = lambda rid: (f'{scope} request_context(input: {{ command: "git push" }}) '
                        f'Agent::Action::"Push"::request(input: {{ command: "git push" }}, {caller}, requestId: "{rid}")')
    trace = WORK / "trace.log"                        # the window is in seconds: a push 60 s after, and 3600 s after
    trace.write_text(f"@1000 {tests('true', 'r1')}\n@1060 {push('r2')}\n@4660 {push('r3')}\n")
    r = run(["dogwood", "replay", str(d / "policy.dw"), "--policy-schema", str(d / "schema.cedarschema"), "--trace", str(trace)])
    verdicts = re.findall(r"\(time point \d+\): (ALLOW|DENY)", r.stdout)
    ok(verdicts == ["ALLOW", "DENY"], "Dogwood: within 15m in seconds (allow at +60 s, deny at +3600 s)", r.stdout + r.stderr)
    gate = WORK / "dwgate.sh"
    gate.write_text(skel("dogwood_gate.sh").replace("<rule id>: <the rule>; <what must happen first>",
                                                    "R0: push only after a passing test run"))
    steps = [("response", tests("true", "g1"), 0), ("request", push("g2"), 0),
             ("response", tests("false", "g3"), 0), ("request", push("g4"), 1)]
    got = [run(["bash", str(gate), kind, event]).returncode for kind, event, _ in steps]
    ok(got == [want for *_, want in steps], "skeleton dogwood_gate.sh: allows after a pass, refuses after a failure",
       f"exit codes {got}")


def wrapper_and_git_hook() -> None:
    Path("/usr/bin/demo-tool").write_text("#!/bin/bash\necho ran \"$@\"\n")
    os.chmod("/usr/bin/demo-tool", 0o755)
    w = skel("wrapper.sh").replace("<program>", "demo-tool").replace("<forbidden argument>", "--force") \
                          .replace("<rule id>: <the rule>; <what to do instead>", "R0: no --force; run it without --force")
    Path("/usr/local/bin/demo-tool").write_text(w)
    os.chmod("/usr/local/bin/demo-tool", 0o755)
    bad = run(["bash", "-lc", "demo-tool --force"], user="agent")
    good = run(["bash", "-lc", "demo-tool x"], user="agent")
    ok(bad.returncode == 1 and "no --force" in bad.stderr and good.stdout.strip() == "ran x",
       "skeleton wrapper.sh, as agent", bad.stderr + good.stdout)

    run(["git", "config", "--system", "core.hooksPath", "/opt/enforce/git-hooks"])
    Path("/opt/enforce/git-hooks").mkdir(parents=True, exist_ok=True)
    Path("/opt/enforce/git-hooks/pre-commit").write_text(skel("pre-commit.sh").replace("<check>", "! grep -q TODO"))
    os.chmod("/opt/enforce/git-hooks/pre-commit", 0o755)
    repo = Path("/home/agent/repo")
    script = (f"set -e; rm -rf {repo}; mkdir -p {repo}; cd {repo}; git init -q; git config user.email a@b.c; "
              "git config user.name a; echo ok > a.txt; git add a.txt; git commit -qm one; "
              "echo TODO > b.txt; git add b.txt; git commit -qm two && echo COMMITTED || echo REFUSED")
    done = run(["bash", "-c", script], user="agent")
    ok("REFUSED" in done.stdout and "COMMITTED" not in done.stdout, "skeleton pre-commit.sh, as agent",
       done.stdout + done.stderr)


def watcher_and_permissions() -> None:
    log = Path("/var/lib/enforce-state/watch.log")
    Path("/var/lib/enforce-state").mkdir(mode=0o700, exist_ok=True)
    Path("/workspace").mkdir(exist_ok=True)
    run(["chmod", "1777", "/workspace"])                        # root's, sticky, as scripts/runner.py sets it
    w = skel("watcher.sh").replace("<check>", "! grep -q TODO").replace(
        "<act: put the file back from a copy, or write a note>",
        'echo "VIOLATION $f"')
    subprocess.Popen(["bash", "-c", w], env=ENV)
    time.sleep(4)
    run(["bash", "-c", "echo TODO > /workspace/w.txt; echo fine > /workspace/v.txt"], user="agent")
    time.sleep(4)
    text = log.read_text() if log.exists() else ""
    ok("VIOLATION /workspace/w.txt" in text and "v.txt" not in text, "skeleton watcher.sh sees the agent's write", text)

    protected = Path("/workspace/root-file.txt")             # sticky /workspace: root's file stays root's
    protected.write_text("root's\n")
    done = run(["bash", "-c", f"mv {protected} /workspace/moved.txt; rm -f {protected}; echo x > {protected}"],
               user="agent")
    ok(protected.read_text() == "root's\n" and not Path("/workspace/moved.txt").exists(),
       "sticky /workspace: the agent cannot change, move or remove root's file", done.stderr)
    locked = Path("/opt/enforce/locked")
    locked.mkdir(exist_ok=True)
    (locked / "f.txt").write_text("root's\n")
    run(["chown", "-R", "root:root", str(locked)])
    run(["chmod", "0755", str(locked)])
    run(["chmod", "0644", str(locked / "f.txt")])
    done = run(["bash", "-c", f"echo x > {locked}/f.txt"], user="agent")
    ok(done.returncode != 0 and "Permission denied" in done.stderr, "file permissions stop the agent's write", done.stderr)


def names() -> None:
    py = "class Box:\n    def open(self):\n        pass\n\nasync def run():\n    return 1\n"
    done = run([sys.executable, "-c", f"text = {py!r}\n" + skel("names_python.py")])
    got = sorted(tuple(line.split()) for line in done.stdout.splitlines())
    ok(got == [("AsyncFunctionDef", "run", "5", "6"), ("ClassDef", "Box", "1", "3"), ("FunctionDef", "open", "2", "3")],
       "skeleton names_python.py", done.stdout + done.stderr)
    js = "function Alpha() {}\nclass Delta {\n  epsilon() {}\n}\n"
    done = run(["/opt/enforce/tool-installs/js-parser/bin/python", "-c", f"text = {js!r}\n" + skel("names_js.py")])
    got = [line.split()[1] for line in done.stdout.splitlines()]
    ok(got == ["Alpha", "Delta", "epsilon"], "skeleton names_js.py (tree-sitter)", done.stdout + done.stderr)


def graph() -> None:
    """Every link in a node resolves in the container, and every recipe a node names exists."""
    import json
    g = json.loads((LIB / "graph.json").read_text())
    bad = [e for e in g["edges"] if not e["to"].startswith("recipe:") and not (LIB / e["to"]).exists()]
    recipes = {n["id"] for n in g["nodes"] if n["kind"] == "recipe"}
    bad += [e for e in g["edges"] if e["to"].startswith("recipe:") and e["to"] not in recipes]
    ok(not bad and len(g["nodes"]) > 200, f"graph.json: {len(g['nodes'])} nodes, {len(g['edges'])} edges, every link resolves",
       str(bad[:5]))


def service() -> None:
    """The root service: an agent-side part asks it; it decides and keeps its history root-only."""
    rule = ('    command = str((request.get("action") or {}).get("command", ""))\n'
            '    if "--force" in command:\n'
            '        return False, "R0: no --force; run it without --force"\n'
            '    return True, ""\n')
    code = skel("service.py").replace("<name>", "demo").replace('    return True, ""\n', rule, 1)
    (WORK / "service.py").write_text(code)
    subprocess.Popen([sys.executable, str(WORK / "service.py")], env=ENV)
    for _ in range(50):
        if Path("/run/enforce/demo.sock").exists():
            break
        time.sleep(0.2)
    client = WORK / "ask_service.py"
    client.write_text(skel("ask_service.py").replace("<name>", "demo"))
    os.chmod(WORK, 0o755)
    client.chmod(0o755)
    bad = run([sys.executable, str(client), "R0"], user="agent", input='{"command": "git push --force"}')
    good = run([sys.executable, str(client), "R0"], user="agent", input='{"command": "git status"}')
    hist = run(["cat", "/var/lib/enforce-state/demo/history.jsonl"], user="agent")
    ok(bad.returncode == 1 and "no --force" in bad.stderr and good.returncode == 0 and hist.returncode != 0,
       "skeletons service.py + ask_service.py, asked as agent (its history root-only)",
       bad.stderr + good.stderr + hist.stdout)


if __name__ == "__main__":
    run(["useradd", "-m", "-u", "1000", "agent"])
    for test in (recipes, check_script, regexes, tool_checks, policies, wrapper_and_git_hook, watcher_and_permissions, service, names,
                 graph):
        try:
            test()
        except Exception as e:                                   # one failing part must not hide the others
            ok(False, test.__name__, f"{type(e).__name__}: {e}")
    failed = [n for good, n in RESULTS if not good]
    print(f"\n{len(RESULTS) - len(failed)} of {len(RESULTS)} passed" + (f"; failed: {', '.join(failed)}" if failed else ""))
    sys.exit(1 if failed else 0)
