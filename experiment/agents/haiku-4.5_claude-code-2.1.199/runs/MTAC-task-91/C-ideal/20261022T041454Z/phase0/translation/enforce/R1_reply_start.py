"""R1: 每次给用户生成回复时，必须首先输出"喵～"这一语气词 (every reply begins with 喵～).
Regex validator on the start of the reply.   R1_reply_start.py - < REPLY"""
import re
import sys

sys.path.insert(0, "/opt/enforce")
from common import cli                                          # noqa: E402

START = re.compile(r"\A\s*喵～")


def problems(text: str, where: str) -> list[str]:
    if START.search(text):
        return []
    first = text.strip()[:20].replace("\n", " ")
    return [f"R1 {where}: it begins with '{first}'; the reply must begin with 喵～ (its very first characters)"]


if __name__ == "__main__":
    cli(problems)
