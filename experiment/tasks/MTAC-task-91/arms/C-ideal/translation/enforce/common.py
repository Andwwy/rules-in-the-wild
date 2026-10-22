"""Shared by the rule checks and the hooks: which files are code files, their comment syntax, and the check.py command
line (/opt/enforce-toolbox/skeletons/check.py). Which files: from the file's name, by GitHub Linguist's kinds:
programming and markup languages count; documents and data do not; a file whose name says neither is decided by its
content: a script's #! line makes it code (an output file such as `0` is not). The agent's own prose in a reply: prose()."""
from __future__ import annotations

import os
import re
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
COMMENT_STARTS = ("#", "//", "/*", "*", "<!--", "--", ";")
# How a comment line starts in each comment form (a C-like block comment's inner lines start with *)
OPENERS = {"# {}": ("#",), "// {}": ("//", "/*", "*"), "/* {} */": ("/*", "*"), "<!-- {} -->": ("<!--",),
           "-- {}": ("--",)}


def comment_form(path: str) -> str | None:
    """The file's comment form when its name says it is code, else None."""
    name = os.path.basename(path)
    return CODE_NAMES.get(name) or CODE.get(os.path.splitext(name)[1].lower())


def known_not_code(path: str) -> bool:
    name = os.path.basename(path)
    return os.path.splitext(name)[1].lower() in NOT_CODE or name in NOT_CODE_NAMES or name.startswith(".env")


def openers(path: str) -> tuple[str, ...]:
    """How a comment line starts in this file's own syntax (any comment form for a script known by its #! line)."""
    form = comment_form(path)
    return OPENERS[form] if form else COMMENT_STARTS


def is_code(path: str, content: bytes | None = None) -> bool:
    if known_not_code(path):
        return False
    if content is None:
        try:
            with open(path, "rb") as f:
                content = f.read(4096)
        except OSError:
            return False
    if b"\0" in content[:4096]:                                # a binary file is not code
        return False
    return comment_form(path) is not None or content.lstrip(b"\xef\xbb\xbf").startswith(b"#!")


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


# What in a reply is not the agent's own prose: code (fenced, inline), markup tags, links, paths and file names; and,
# with quotes=True, quoted text (another's words, a UI text, a term)
NOT_OWN = [re.compile(r"```.*?(?:```|\Z)|~~~.*?(?:~~~|\Z)|`[^`\n]*`", re.S),
           re.compile(r"</?[A-Za-z][\w:-]*(?:\s[^<>\n]*)?/?>"),
           re.compile(r"https?://\S+"),
           re.compile(r"(?:\.{0,2}/)?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+|[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+")]
QUOTED = re.compile(r"“[^”\n]*”|\"[^\"\n]*\"|「[^」\n]*」|『[^』\n]*』|‘[^’\n]*’")


def prose(text: str, quotes: bool = True) -> str:
    """The reply with everything that is not the agent's own prose blanked out, at the same length and line breaks,
    so that a position in it is the same position in the reply."""
    def blank(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))
    for pattern in NOT_OWN + ([QUOTED] if quotes else []):
        text = pattern.sub(blank, text)
    return text


def cli(problems) -> None:
    """check.py's command line: `check FILE ...` or `check - < TEXT`. Exit 1 with each violation on stderr."""
    items = [(sys.stdin.read(), "the reply")] if sys.argv[1:] == ["-"] else [(read(f), f) for f in sys.argv[1:]]
    found = [p for text, where in items for p in problems(text, where)]
    print("\n".join(found), file=sys.stderr)
    sys.exit(1 if found else 0)
