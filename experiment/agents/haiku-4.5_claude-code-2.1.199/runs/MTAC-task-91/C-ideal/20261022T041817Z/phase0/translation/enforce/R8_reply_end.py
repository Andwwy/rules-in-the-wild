"""R8: 你的所有回复都必须在结尾处加上"哒～"语气词 (every reply ends with 哒～).
Regex validator on the end of the reply.   R8_reply_end.py - < REPLY"""
import re
import sys

sys.path.insert(0, "/opt/enforce")
from common import cli                                          # noqa: E402

END = re.compile(r"哒～\s*\Z")


def problems(text: str, where: str) -> list[str]:
    if END.search(text):
        return []
    last = text.strip()[-20:].replace("\n", " ")
    return [f"R8 {where}: it ends with '{last}'; the reply must end with 哒～ (its very last characters)"]


if __name__ == "__main__":
    cli(problems)
