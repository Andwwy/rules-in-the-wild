"""Shared by the rule checks and the hooks: which files are code files, their comment syntax, and the check.py command
line (/opt/enforce-toolbox/skeletons/check.py). Which files: from the file's name, by GitHub Linguist's kinds:
programming and markup languages count; documents and data do not; a text file of unknown kind is checked, not passed."""
from __future__ import annotations

import os
import sys

WORKSPACE = "/workspace"
# Directories that hold no file the agent wrote: installed packages, version control, caches
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", ".cache", ".pytest_cache", ".claude", ".npm"}
# Code: extension -> comment form ("{}" is the comment's text)
CODE = {
    **dict.fromkeys((".py", ".pyw", ".sh", ".bash", ".zsh", ".rb", ".pl", ".r", ".ps1", ".mk"), "# {}"),
    **dict.fromkeys((".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".mts", ".cts", ".java", ".kt", ".kts", ".scala",
                     ".go", ".rs", ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".cs", ".swift", ".dart", ".php",
                     ".scss", ".sass", ".less"), "// {}"),
    ".css": "/* {} */",
    **dict.fromkeys((".html", ".htm", ".xhtml", ".vue", ".svelte"), "<!-- {} -->"),
    **dict.fromkeys((".sql", ".lua", ".hs"), "-- {}"),
}
CODE_NAMES = {"Makefile": "# {}", "Dockerfile": "# {}", "Rakefile": "# {}", "Gemfile": "# {}"}
# Documents and data (not code), and binary files
NOT_CODE = {".md", ".markdown", ".rst", ".txt", ".json", ".jsonc", ".json5", ".yaml", ".yml", ".csv", ".tsv", ".lock",
            ".log", ".xml", ".svg", ".ini", ".toml", ".cfg", ".conf", ".env", ".map", ".pdf", ".zip", ".gz", ".tgz",
            ".tar", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".mp3", ".mp4", ".wav", ".webm", ".woff",
            ".woff2", ".ttf", ".otf", ".eot", ".pyc", ".so", ".o", ".db", ".sqlite", ".tsbuildinfo", ".snap", ".patch",
            ".diff"}
NOT_CODE_NAMES = {"LICENSE", "README", "CHANGELOG", "AUTHORS", "CODEOWNERS", ".gitignore", ".gitattributes", ".npmrc",
                  ".nvmrc", ".editorconfig", ".prettierrc", ".prettierignore", ".eslintignore", ".dockerignore",
                  ".last-run.json"}
COMMENT_STARTS = ("#", "//", "/*", "*", "<!--", "--", ";", '"""', "'''")


def comment_form(path: str) -> str | None:
    """The file's comment form if it is a code file, else None. Unknown kind: a code file, with `#` comments."""
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    if name in CODE_NAMES:
        return CODE_NAMES[name]
    if ext in CODE:
        return CODE[ext]
    if ext in NOT_CODE or name in NOT_CODE_NAMES or name.startswith(".env"):
        return None
    return "# {}"


def is_code(path: str, content: bytes | None = None) -> bool:
    if comment_form(path) is None:
        return False
    if content is None:
        try:
            with open(path, "rb") as f:
                content = f.read(4096)
        except OSError:
            return False
    return b"\0" not in content[:4096]                         # a binary file is not code


def code_files(root: str = WORKSPACE) -> list[str]:
    """Every code file under root, as it is on disk now."""
    out = []
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
        out += [os.path.join(d, f) for f in sorted(files) if os.path.isfile(os.path.join(d, f))
                and is_code(os.path.join(d, f))]
    return out


def read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def cli(problems) -> None:
    """check.py's command line: `check FILE ...` or `check - < TEXT`. Exit 1 with each violation on stderr."""
    items = [(sys.stdin.read(), "the reply")] if sys.argv[1:] == ["-"] else [(read(f), f) for f in sys.argv[1:]]
    found = [p for text, where in items for p in problems(text, where)]
    print("\n".join(found), file=sys.stderr)
    sys.exit(1 if found else 0)
