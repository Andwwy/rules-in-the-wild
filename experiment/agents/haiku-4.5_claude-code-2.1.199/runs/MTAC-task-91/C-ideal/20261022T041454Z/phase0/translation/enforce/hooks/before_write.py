"""PreToolUse on Write, Edit and MultiEdit: R5 (pre-commit) and R7 (Semgrep) on the file as the tool would leave it,
before it is written (their routes: File write / edit, before). A violation refuses the tool call."""
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, "/opt/enforce")
import R7_function_length                                       # noqa: E402
from common import WORKSPACE, is_code                           # noqa: E402


def new_content(tool: str, inp: dict) -> str | None:
    """The file's content after the tool call; None when the call would fail anyway (the tool says why)."""
    if tool == "Write":
        return inp.get("content", "")
    try:
        with open(inp["file_path"], encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        text = ""
    edits = inp.get("edits") if tool == "MultiEdit" else [inp]
    for e in edits or []:
        old, new = e.get("old_string", ""), e.get("new_string", "")
        if old == "" and text == "":
            text = new
        elif old in text:
            text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
        else:
            return None
    return text


def r5(path: str, content: str) -> list[str]:
    """R5 by pre-commit on the new content, at the file's place relative to the project."""
    rel = os.path.relpath(path, WORKSPACE) if path.startswith(WORKSPACE + "/") else os.path.basename(path)
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, os.path.dirname(rel)), exist_ok=True)
        with open(os.path.join(root, rel), "w", encoding="utf-8") as f:
            f.write(content)
        done = subprocess.run(["/bin/bash", "/opt/enforce/R5_pre_commit.sh", root, rel], capture_output=True, text=True)
    lines = [x.replace(f"R5 {rel}:", f"R5 {path}:", 1) for x in done.stdout.splitlines() if x.startswith("R5 ")]
    if done.returncode and not lines:
        raise RuntimeError(f"pre-commit failed (exit {done.returncode}): {(done.stdout + done.stderr)[-600:]}")
    return lines


def main() -> int:
    event = json.load(sys.stdin)
    tool, inp = event.get("tool_name", ""), event.get("tool_input") or {}
    path = inp.get("file_path") or ""
    content = new_content(tool, inp) if path else None
    if content is None or not is_code(path, content.encode("utf-8", "replace")):
        return 0
    found = r5(path, content) + R7_function_length.check([(path, content)])
    if found:
        reason = ("Refused by the project's enforcement of CLAUDE.md: the file would break these rules. Nothing was "
                  "written. Fix all of them and write the file again.\n" + "\n".join(found))
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": reason}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
