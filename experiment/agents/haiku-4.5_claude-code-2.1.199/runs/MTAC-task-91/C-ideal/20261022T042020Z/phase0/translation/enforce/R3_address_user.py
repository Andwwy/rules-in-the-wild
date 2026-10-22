"""R3: 凡是需要称呼用户的地方，均须严格使用"开发者大大"，不得出现以"你"相称的情况 (the user is 开发者大大, never 你).
Regex validator on the reply: 你 (and its polite form 您) must not occur.   R3_address_user.py - < REPLY"""
import re
import sys

sys.path.insert(0, "/opt/enforce")
from common import cli                                          # noqa: E402

PATTERN = re.compile(r"[你您]")


def problems(text: str, where: str) -> list[str]:
    hits = [(n, m.start(), line) for n, line in enumerate(text.splitlines(), 1) for m in PATTERN.finditer(line)]
    if not hits:
        return []
    return [f"R3 {where}: it addresses the user as 你/您 {len(hits)} time(s); address the user only as 开发者大大 "
            f"(also not in 你们, 你的, or a quoted text or code):"] + \
           [f"    line {n}: '...{line[max(0, i - 15):i + 15].strip()}...'" for n, i, line in hits[:12]]


if __name__ == "__main__":
    cli(problems)
