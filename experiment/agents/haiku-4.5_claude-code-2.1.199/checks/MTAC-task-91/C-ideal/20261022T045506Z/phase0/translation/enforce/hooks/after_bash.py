"""PostToolUse on Bash: R5 and R7 on every code file of the project as the command left it (on_disk.py). A shell
command's writes cannot be seen before it runs; this is the earliest moment they can be checked."""
import json
import sys

sys.path.insert(0, "/opt/enforce/hooks")
from on_disk import r5_r7                                       # noqa: E402


def main() -> int:
    json.load(sys.stdin)
    found = r5_r7()
    if found:
        reason = ("The project's enforcement of CLAUDE.md: after this command, these code files break its rules. Fix "
                  "every one now; the turn cannot end while they do (a file that a tool generated and the project "
                  "does not need: delete it, or keep it out of /workspace).\n" + "\n".join(found))
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
