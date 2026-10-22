"""R5: 无论生成哪个代码文件，其起始第一行都必须严格添加 -*- coding: utf-8 -*- 以声明编码 (a code file's first line declares
-*- coding: utf-8 -*-, as a comment in the file's own syntax: the source-file card). The check that pre-commit runs on each file (R5_pre_commit.sh).   R5_coding_line.py FILE ..."""
import sys

sys.path.insert(0, "/opt/enforce")
from common import cli, comment_form, openers                   # noqa: E402

DECLARATION = "-*- coding: utf-8 -*-"


def problems(text: str, where: str) -> list[str]:
    first = text.split("\n", 1)[0].strip().lstrip("\ufeff")
    if DECLARATION in first and first.startswith(openers(where)):
        return []
    line = (comment_form(where) or "# {}").format(DECLARATION)
    return [f"R5 {where}:1: the first line is '{first[:60]}'; line 1 of every code file must be the encoding "
            f"declaration, as a comment in the file's own syntax, here: {line}"]


if __name__ == "__main__":
    cli(problems)
