"""Configuration: the dataset, the credentials, and the parser identity.

A `.env` next to this project is loaded with setdefault-only semantics (never overrides a
real environment variable). Nothing here imports a database driver — the Hugging Face
dataset is the only store this project touches.
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(_env_path):
    for _l in open(_env_path):
        _l = _l.strip()
        if _l and not _l.startswith("#") and "=" in _l:
            _k, _v = _l.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# A WRITE-scoped token is required to push. Reads of a public dataset work without one.
HF_TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")

HF_REPO_ID = os.environ.get("HF_RULES_REPO", "Andwwy/rules")
HF_REVISION = os.environ.get("HF_RULES_REVISION", "main")

# Folder layout inside the dataset repo. `files` is the rule_file corpus (read-only to
# this project); `clauses` is what the parser produces.
FILES_DIR = os.environ.get("HF_FILES_DIR", "data")
CLAUSES_DIR = os.environ.get("HF_CLAUSES_DIR", "clauses")

# Column of the files config carrying the document text. The corpus calls it `file`.
FILES_TEXT_COLUMN = os.environ.get("HF_FILES_TEXT_COLUMN", "file")

# ── MotherDuck input source ───────────────────────────────────────────────────────────
# Optional alternative to reading rule files from Hugging Face. Reads only — clauses are
# still written to the HF dataset. Set MOTHERDUCK_TOKEN in .env to enable.
MOTHERDUCK_TOKEN = os.environ.get("MOTHERDUCK_TOKEN") or os.environ.get("motherduck_token")
MOTHERDUCK_DB = os.environ.get("MOTHERDUCK_DB", "rules")
MD_FILES_TABLE = os.environ.get("MD_FILES_TABLE", "rule_file")

# canonical column -> column in the MotherDuck table. `rules.rule_file` already uses the
# same names as the Hugging Face corpus, so this is an identity mapping and the rename is
# a no-op. It stays configurable because a differently-shaped table (e.g. the crawler's
# `files`, which uses repo_name/file_path/content_hash/content) then needs no code change.
# An empty value means "column not present" — `stars` would default to 0.
MD_COLUMNS = {
    "repo":           os.environ.get("MD_REPO_COLUMN", "repo"),
    "path":           os.environ.get("MD_PATH_COLUMN", "path"),
    "link":           os.environ.get("MD_LINK_COLUMN", "link"),
    "content_sha256": os.environ.get("MD_SHA_COLUMN", "content_sha256"),
    FILES_TEXT_COLUMN: os.environ.get("MD_TEXT_COLUMN", "file"),
    "stars":          os.environ.get("MD_STARS_COLUMN", "stars"),
}

# ── parser identity ───────────────────────────────────────────────────────────────────
# Stamped onto every clause. BUMP THE VERSION whenever the grammar changes: the runner
# re-cuts any file whose stored clauses carry a different (grammar, parser_version), so
# a bump is the switch that reprocesses the corpus.
GRAMMAR = os.environ.get("CLAUSE_GRAMMAR", "v2")
PARSER_VERSION = "2.2.0"   # 2.2.0 (audit of 1,000 sampled clauses): terminals consume
                           # trailing closers; quoted literals / paren groups / line-start
                           # enumerators / HTML comments protected; CJK terminals split;
                           # colon-at-EOL and **Label**: line boundaries; fullwidth-colon
                           # lead-ins; `markup` type; bold-label pseudo-headings; YAML
                           # comments skipped; literal \n escapes bound field leaves;
                           # semicolons split only sentence-like parts (>=4 words each
                           # side); non-NL front-matter leaves typed `field_meta`.
                           # 2.1.0: front-matter leaves; lead_in; table_row structural

# Largest document treated as a single rule file. Beyond this it is a dataset dump, not
# an agent-rules file, and would explode into a pathological number of clauses.
MAX_CONTENT_BYTES = 512 * 1024

# Parquet shard size — keeps a single commit from ever carrying a huge blob.
MAX_ROWS_PER_SHARD = 100_000


# ── file_type taxonomy ────────────────────────────────────────────────────────────────
# The known conventions for "a natural-language rules file for an LLM agent". Data-driven
# so a new IDE shipping a new rules filename is a one-line change. Anything outside the
# taxonomy falls back to its own basename rather than being dropped (the HF corpus is
# broader than this list — SKILL.md, for instance).
RULE_BASENAMES = {
    "claude.md": "CLAUDE.md", "claude.local.md": "CLAUDE.md",
    "agents.md": "AGENTS.md", "agent.md": "AGENTS.md",
    "gemini.md": "GEMINI.md", "qwen.md": "QWEN.md",
    "skill.md": "SKILL.md",
    ".cursorrules": ".cursorrules", "cursorrules": "cursorrules",
    ".windsurfrules": ".windsurfrules", ".clinerules": ".clinerules",
    ".roorules": ".roorules", ".rules": ".rules", ".goosehints": ".goosehints",
    ".aider.conf.yml": ".aider.conf.yml",
    "copilot-instructions.md": "copilot-instructions.md",
    "rules.md": "RULES.md", "conventions.md": "CONVENTIONS.md",
    "prompt.md": "PROMPT.md", "system_prompt.md": "SYSTEM_PROMPT.md",
    "system-prompt.md": "system-prompt.md",
    "llms.txt": "llms.txt", "llms-full.txt": "llms-full.txt",
}
RULE_PATH_PATTERNS = (
    (".cursor/rules/", "mdc"),
    (".github/copilot-instructions.md", ".github/copilot-instructions.md"),
    (".github/instructions/", "instructions.md"),
    (".continue/", ".continue/config.json"),
    (".clinerules/", ".clinerules"),
    (".roo/rules", ".roorules"),
    (".junie/guidelines.md", "guidelines.md"),
    (".idx/airules.md", "airules.md"),
)


def classify(path):
    """Normalized file_type label for a path. Falls back to the basename for files
    outside the known taxonomy, so nothing is silently discarded."""
    p = (path or "").replace("\\", "/").lower()
    base = p.rsplit("/", 1)[-1]
    if base in RULE_BASENAMES:
        return RULE_BASENAMES[base]
    if base.endswith(".mdc"):
        return "mdc"
    if base.endswith(".instructions.md"):
        return "instructions.md"
    for frag, label in RULE_PATH_PATTERNS:
        if frag in p:
            return label
    return (path or "").replace("\\", "/").rsplit("/", 1)[-1]


__all__ = ["BASE_DIR", "HF_TOKEN", "HF_REPO_ID", "HF_REVISION", "FILES_DIR", "CLAUSES_DIR",
           "FILES_TEXT_COLUMN", "GRAMMAR", "PARSER_VERSION", "MAX_CONTENT_BYTES",
           "MAX_ROWS_PER_SHARD", "classify",
           "MOTHERDUCK_TOKEN", "MOTHERDUCK_DB", "MD_FILES_TABLE", "MD_COLUMNS"]
