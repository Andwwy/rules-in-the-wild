"""The clause schema — one row per clause cut out of a rule file.

Three ids, each answering a different question:

  file_id      sha256(repo, path)[:16] — WHICH FILE, stable across edits, so one file's
               clauses can be tracked over revisions.
  clause_id    sha256(file_id, content_sha256, idx, char_start, char_end)[:16] — WHICH
               CLAUSE OF WHICH REVISION. Content-versioned on purpose: re-cutting
               unchanged text reproduces the same ids (idempotent insert), while edited
               text yields fresh ones so a stale clause cannot pass as current.
  text_sha256  sha256(whitespace-normalized clause_text) — WHICH WORDING, corpus-wide.
               Two repos that copy the same rule share it, making "how often is this
               repeated?" a GROUP BY instead of a fuzzy match.

Provenance (repo, path, link, stars, file_type) is denormalized onto every clause: a
Hugging Face config is loaded on its own, so a row carrying only a foreign key would be
unusable without a second download and a manual join.

Position is stored twice deliberately — char offsets are exact and are what an annotation
UI anchors to; line numbers are what a human reads and what `link#L12` resolves to.

`grammar` + `parser_version` are the re-cut switch: rows carry the identity of the code
that produced them, so bumping the version tells the runner these clauses are stale.
"""
import hashlib
import re

import pyarrow as pa

# Declared explicitly (not inferred) so every shard any run writes is byte-compatible and
# concatenation never has to promote a type.
CLAUSE_SCHEMA = pa.schema([
    # ── identity ──────────────────────────────────────────────────────────────────────
    ("clause_id",      pa.string()),    # this clause, in this revision of this file
    ("file_id",        pa.string()),    # the file, stable across revisions
    ("text_sha256",    pa.string()),    # the wording, across the whole corpus
    # ── provenance (denormalized — keeps the clauses config self-contained) ────────────
    ("repo",           pa.string()),
    ("path",           pa.string()),
    ("link",           pa.string()),    # permalink to the exact blob (commit-pinned)
    ("stars",          pa.int64()),
    ("file_type",      pa.string()),    # CLAUDE.md, AGENTS.md, SKILL.md, mdc, .cursorrules…
    ("content_sha256", pa.string()),    # the file revision this clause was cut from
    # ── location within the file ──────────────────────────────────────────────────────
    ("idx",            pa.int32()),     # 1-based unit index, document order
    ("char_start",     pa.int32()),     # exact: clause_text == content[char_start:char_end]
    ("char_end",       pa.int32()),
    ("line_start",     pa.int32()),
    ("line_end",       pa.int32()),
    # ── the clause ────────────────────────────────────────────────────────────────────
    ("clause_text",    pa.string()),    # verbatim slice of the file
    ("unit_type",      pa.string()),    # heading|code|table_header|table_row|field|statement|clause|lead_in|markup|field_meta
    ("is_structural",  pa.bool_()),     # True for skeleton (heading/code/table header)
    ("heading_path",   pa.string()),    # "Usage > Testing" ("" at top level)
    ("heading_depth",  pa.int32()),     # segments in heading_path (0 = preamble)
    ("n_chars",        pa.int32()),
    ("n_words",        pa.int32()),
    # ── parser lineage ────────────────────────────────────────────────────────────────
    ("grammar",        pa.string()),    # v1 | v2
    ("parser_version", pa.string()),    # bump in config.py to force a re-cut
    ("run_id",         pa.string()),
    ("extracted_at",   pa.timestamp("us", tz="UTC")),
])

COLUMNS = [f.name for f in CLAUSE_SCHEMA]

# "This file, at this revision, cut by this grammar" — the already-extracted check.
EXTRACTION_KEY = ("file_id", "content_sha256", "grammar", "parser_version")

_WS = re.compile(r"\s+")


def _sha(*parts):
    return hashlib.sha256(":".join("" if p is None else str(p) for p in parts).encode("utf-8")).hexdigest()


def make_file_id(repo, path):
    """Stable id for a rule file — content-independent, so it survives edits."""
    return _sha(repo, path)[:16]


def make_clause_id(file_id, content_sha256, idx, char_start, char_end):
    """Stable id for one clause of one revision. Idempotent on unchanged content."""
    return _sha(file_id, content_sha256, idx, char_start, char_end)[:16]


def make_text_sha256(clause_text):
    """Wording id: whitespace-normalized (so hard wrapping doesn't matter), case kept."""
    return hashlib.sha256(_WS.sub(" ", (clause_text or "").strip()).encode("utf-8")).hexdigest()


def to_table(rows):
    """Schema-conformant pyarrow Table from clause dicts. Raises on a missing or
    unexpected column so a malformed row fails here, not inside a shard."""
    rows = list(rows)
    if not rows:
        return CLAUSE_SCHEMA.empty_table()
    for i, r in enumerate(rows):
        missing = [c for c in COLUMNS if c not in r]
        extra = [c for c in r if c not in COLUMNS]
        if missing or extra:
            raise ValueError(
                f"clause row {i} does not match the schema"
                + (f" — missing {missing}" if missing else "")
                + (f" — unexpected {extra}" if extra else ""))
    return pa.Table.from_pydict({c: [r[c] for r in rows] for c in COLUMNS}, schema=CLAUSE_SCHEMA)


def describe():
    return "\n".join(f"  {f.name:<16} {str(f.type)}" for f in CLAUSE_SCHEMA)


__all__ = ["CLAUSE_SCHEMA", "COLUMNS", "EXTRACTION_KEY", "make_file_id", "make_clause_id",
           "make_text_sha256", "to_table", "describe"]
