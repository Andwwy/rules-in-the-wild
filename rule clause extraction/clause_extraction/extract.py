"""One rule file → its clauses. The parser applied to a single document.

Side-effect free: no network, no database, no clock beyond the single `extracted_at`
stamp passed in — so the same file row always produces the same clause rows, with the
same ids. Every unit the grammar emits becomes a row; nothing is judged to be "a rule"
or not. Structural units (headings, code, table rows, colon lead-ins) are kept and
flagged via `is_structural` so the segmentation stays lossless and consumers filter
downstream.
"""
from datetime import datetime, timezone

from .config import (FILES_TEXT_COLUMN, GRAMMAR, MAX_CONTENT_BYTES, PARSER_VERSION,
                     classify)
from .grammar import (STRUCTURAL_TYPES, _line_offsets, heading_path_at, heading_spans,
                      line_of, segment)
from .schema import make_clause_id, make_file_id, make_text_sha256


def extract_clauses(file_row, run_id, grammar=None, extracted_at=None):
    """Cut one file row (a dict from the files config) into clause rows."""
    grammar = grammar or GRAMMAR
    content = file_row.get(FILES_TEXT_COLUMN) or ""
    repo, path = file_row.get("repo") or "", file_row.get("path") or ""
    content_sha256 = file_row.get("content_sha256") or ""
    fid = make_file_id(repo, path)
    ftype = classify(path)
    ts = extracted_at or datetime.now(timezone.utc)

    line_offsets = _line_offsets(content)
    headings = heading_spans(content)
    heading_starts = {h[0] for h in headings}

    rows = []
    for u in segment(content, grammar):
        cs, ce = u["char_start"], u["char_end"]
        text = u["text"]
        crumb = heading_path_at(headings, cs, cs in heading_starts)
        rows.append({
            "clause_id": make_clause_id(fid, content_sha256, u["idx"], cs, ce),
            "file_id": fid,
            "text_sha256": make_text_sha256(text),
            "repo": repo,
            "path": path,
            "link": file_row.get("link") or "",
            "stars": int(file_row.get("stars") or 0),
            "file_type": ftype,
            "content_sha256": content_sha256,
            "idx": int(u["idx"]),
            "char_start": int(cs),
            "char_end": int(ce),
            "line_start": line_of(line_offsets, cs),
            "line_end": line_of(line_offsets, max(cs, ce - 1)),
            "clause_text": text,
            "unit_type": u["type"],
            "is_structural": u["type"] in STRUCTURAL_TYPES,
            "heading_path": crumb,
            "heading_depth": len([s for s in crumb.split(" > ") if s]),
            "n_chars": len(text),
            "n_words": len(text.split()),
            "grammar": grammar,
            "parser_version": PARSER_VERSION,
            "run_id": run_id,
            "extracted_at": ts,
        })
    return rows


def skip_reason(file_row):
    """Why this file cannot be cut, or None if it can. Checked before parsing so the
    runner reports a reason instead of writing a degenerate row set."""
    content = file_row.get(FILES_TEXT_COLUMN)
    if not content or not content.strip():
        return "empty content"
    if len(content) > MAX_CONTENT_BYTES:
        return f"too large ({len(content)} bytes)"
    if not (file_row.get("repo") and file_row.get("path")):
        return "missing repo/path (cannot form a stable file_id)"
    if not file_row.get("content_sha256"):
        return "missing content_sha256 (cannot version the clause ids)"
    return None


__all__ = ["extract_clauses", "skip_reason"]
