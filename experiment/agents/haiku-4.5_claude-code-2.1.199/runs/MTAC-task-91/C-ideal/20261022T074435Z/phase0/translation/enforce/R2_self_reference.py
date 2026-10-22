"""R2: 无论何时提到自身，都请始终用"代码小灵"替代"我"来进行自我指代 (the agent calls itself 代码小灵, never 我).
Regex filter on the agent's own prose in the reply (not code, quoted text, links or paths: common.prose): the pronoun
我 (also in 我的) -> 代码小灵. Not the pronoun: 我们 / 我們 ("we", which 代码小灵 cannot replace), and words where 我 is
not the agent (自我, 忘我, 本我, 敌我, 我方, 我国). A Stop hook cannot change the reply, so the filter refuses it and gives
the fixed lines back (the regex filter card's other way).   R2_self_reference.py - < REPLY"""
import re
import sys

sys.path.insert(0, "/opt/enforce")
from common import cli, prose                                   # noqa: E402

PATTERN, REPLACEMENT = re.compile(r"(?<![自忘本敌敵])我(?![们們方国國])"), "代码小灵"


def problems(text: str, where: str) -> list[str]:
    own, fixed, start = prose(text), [], 0
    for n, line in enumerate(text.split("\n"), 1):
        hits = [m.start() for m in PATTERN.finditer(own, start, start + len(line))]
        if hits:
            out, last = [], start
            for i in hits:
                out.append(text[last:i] + REPLACEMENT)
                last = i + 1
            fixed.append((n, ("".join(out) + text[last:start + len(line)]).strip()))
        start += len(line) + 1
    if not fixed:
        return []
    return [f"R2 {where}: it refers to itself as 我 on {len(fixed)} line(s); the agent refers to itself only as "
            f"代码小灵. The filtered lines (我 -> 代码小灵; rephrase if a line reads badly):"] + \
           [f"    line {n}: {line[:200]}" for n, line in fixed[:12]]


if __name__ == "__main__":
    cli(problems)
