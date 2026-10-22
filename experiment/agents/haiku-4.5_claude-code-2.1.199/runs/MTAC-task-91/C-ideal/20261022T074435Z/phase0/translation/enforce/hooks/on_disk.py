"""R5 (pre-commit) and R7 (Semgrep) on every code file of the project as it is on disk: for what shell commands
wrote, which no hook sees before it is written. after_bash.py runs it right after each command (the earliest moment);
end_of_turn.py runs it again, so that the turn cannot end with such a file still breaking a rule."""
import os
import subprocess
import sys

sys.path.insert(0, "/opt/enforce")
import R7_function_length                                       # noqa: E402
from common import WORKSPACE, code_files, read                  # noqa: E402


def r5_r7() -> list[str]:
    files = code_files()
    if not files:
        return []
    rels = [os.path.relpath(f, WORKSPACE) for f in files]
    done = subprocess.run(["/bin/bash", "/opt/enforce/R5_pre_commit.sh", WORKSPACE, *rels], capture_output=True,
                          text=True)
    found = [x.replace("R5 ", f"R5 {WORKSPACE}/", 1) for x in done.stdout.splitlines() if x.startswith("R5 ")]
    if done.returncode and not found:
        raise RuntimeError(f"pre-commit failed (exit {done.returncode}): {(done.stdout + done.stderr)[-600:]}")
    return found + R7_function_length.check([(f, read(f)) for f in files])
