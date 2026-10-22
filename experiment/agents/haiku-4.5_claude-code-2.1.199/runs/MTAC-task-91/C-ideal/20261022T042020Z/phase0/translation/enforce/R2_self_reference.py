"""R2: 无论何时提到自身，都请始终用"代码小灵"替代"我"来进行自我指代 (the agent calls itself 代码小灵, never 我).
Regex filter on the reply: 我 -> 代码小灵. A Stop hook cannot change the reply, so the filter refuses it and gives the
fixed lines back (the regex filter card's other way).   R2_self_reference.py - < REPLY"""
import re
import sys

sys.path.insert(0, "/opt/enforce")
from common import cli                                          # noqa: E402

PATTERN, REPLACEMENT = re.compile(r"我"), "代码小灵"


def problems(text: str, where: str) -> list[str]:
    fixed = [(n, PATTERN.sub(REPLACEMENT, line).strip()) for n, line in enumerate(text.splitlines(), 1)
             if PATTERN.search(line)]
    if not fixed:
        return []
    return [f"R2 {where}: it says 我 on {len(fixed)} line(s); the agent refers to itself only as 代码小灵, never 我 "
            f"(also not in 我们, 我的). The filtered lines (我 -> 代码小灵; rephrase if a line reads badly):"] + \
           [f"    line {n}: {line[:200]}" for n, line in fixed[:12]]


if __name__ == "__main__":
    cli(problems)
