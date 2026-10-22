"""R3: 凡是需要称呼用户的地方，均须严格使用"开发者大大"，不得出现以"你"相称的情况 (the user is 开发者大大, never 你).
Regex validator on the agent's own prose in the reply (not code, quoted text, links or paths: common.prose): the
second person 你 / 您 / 妳 (also in 你们, 你的) addresses the user; 迷你 ("mini") does not.   R3_address_user.py - < REPLY"""
import re
import sys

sys.path.insert(0, "/opt/enforce")
from common import cli, prose                                   # noqa: E402

PATTERN = re.compile(r"(?<!迷)[你您妳]")


def problems(text: str, where: str) -> list[str]:
    own = prose(text)
    hits = [m.start() for m in PATTERN.finditer(own)]
    if not hits:
        return []
    line_of = lambda i: text.count("\n", 0, i) + 1                         # noqa: E731
    return [f"R3 {where}: it addresses the user as 你/您 {len(hits)} time(s); address the user only as 开发者大大:"] + \
           [f"    line {line_of(i)}: '...{text[max(0, i - 12):i + 12].strip()}...'" for i in hits[:12]]


if __name__ == "__main__":
    cli(problems)
