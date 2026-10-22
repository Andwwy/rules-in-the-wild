"""PostToolUse on Bash: R5 (pre-commit) and R7 (Semgrep) on every code file of the project as the command left it. A
shell command's writes cannot be seen before it runs; this is the earliest moment they can be checked."""
import json
import os
import subprocess
import sys

sys.path.insert(0, "/opt/enforce")
import R7_function_length                                       # noqa: E402
from common import WORKSPACE, code_files, read                  # noqa: E402


def main() -> int:
    json.load(sys.stdin)
    files = code_files()
    if not files:
        return 0
    rels = [os.path.relpath(f, WORKSPACE) for f in files]
    done = subprocess.run(["/bin/bash", "/opt/enforce/R5_pre_commit.sh", WORKSPACE, *rels], capture_output=True,
                          text=True)
    found = [x.replace("R5 ", f"R5 {WORKSPACE}/", 1) for x in done.stdout.splitlines() if x.startswith("R5 ")]
    if done.returncode and not found:
        raise RuntimeError(f"pre-commit failed (exit {done.returncode}): {(done.stdout + done.stderr)[-600:]}")
    found += R7_function_length.check([(f, read(f)) for f in files])
    if found:
        reason = ("The project's enforcement of CLAUDE.md: after this command, these code files break its rules. Fix "
                  "every one (a file that a tool generated and the project does not need: delete it, or keep it out "
                  "of /workspace).\n" + "\n".join(found))
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
