"""Export just the natural-language rule text as JSON.

The parser emits every unit of a document, including its skeleton. This selects the
units that are actually prose — the ones a human would read as a written rule — and
writes their text and nothing else.

    python -m clause_extraction.export --files-parquet ./_corpus_cache/part-00000.parquet -o rules.json

WHAT COUNTS AS NL TEXT (deterministic, no judgement about whether a sentence is "a rule"):

    included   statement   a paragraph or list item that is a single sentence
               clause      one sentence of a paragraph that split into several
    excluded   heading     a section title — structure, not a written rule
               code        a fenced block — not natural language at all
               table_header  column names
               table_row   tabular reference data (command tables, option matrices);
                           prose survives in tables only incidentally
               field       YAML front matter — mostly metadata (`name:`, `version:`)
               lead_in     a span ending in ':' — announces the following list, code
                           block, or table and carries no directive of its own
               markup      HTML comments and lone XML/HTML tag lines
               field_meta  non-NL front-matter metadata (`model: sonnet`, tool lists)

`--include field,table_row` adds those back; front matter in particular holds the
`description: Use when …` applicability rule, which is genuine NL.

The text is cleaned only of things that are markup rather than language:
whitespace is collapsed (these files are hard-wrapped, so a clause carries the source's
newlines verbatim) and a leading list marker is dropped. Markdown emphasis inside the
sentence is left alone — removing it would change the author's wording.
"""
import argparse
import json
import re
import sys

from .config import GRAMMAR, FILES_TEXT_COLUMN
from .extract import skip_reason
from .grammar import _MD, segment

NL_TYPES = ("statement", "clause")
_WS = re.compile(r"\s+")
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
# A sentence split can cut a **bold span** in half, leaving an unmatched delimiter that
# the parser — correctly — reports as literal text. After parsing, `\*`, `a * b` and an
# orphaned `**` are ALL a plain text token with no markup: markdown-it cannot tell them
# apart, so neither can we. The sweep is therefore deliberately narrow — only a 2-3 char
# emphasis run at the very START or END of the string, which is the only place a cut
# delimiter can land. A single `*` is never touched, so globs (`*.spec.ts`), products
# (`a * b`) and escapes (`\*`) all survive.
_ORPHAN_EDGE = re.compile(r"^(?:\*{2,3}|_{2,3})\s*|\s*(?:\*{2,3}|_{2,3})$")
_TABLE_PIPE = re.compile(r"\s*\|\s*")


def clean(text):
    """Collapse hard wrapping and drop a leading list marker. Nothing else."""
    return _WS.sub(" ", _BULLET.sub("", text or "").strip()).strip()


def plain(text):
    """Strip markdown markup, using the grammar's own inline parser rather than regex.

    markdown-it tokenizes the span; we keep the payloads and drop the delimiters:
      **bold** / _em_ / ~~del~~ -> the inner text     `code` -> the code, no backticks
      [label](url)              -> label              ![alt](src) -> alt
      <span>, <br/>             -> dropped            soft/hard breaks -> a space

    Regex cannot do this correctly — `` `a * b` `` is not emphasis, `\\*` is a literal
    asterisk, and a link label can itself contain markup. The parser already knows.

    One caveat the parser cannot fix: a sentence split can cut a bold span in half, so an
    unmatched `**` is genuinely literal text at that point. Those orphans are swept up
    afterwards; balanced markup never reaches that step."""
    text = clean(text)
    if not text:
        return ""
    if _MD is None:                                   # degraded mode — leave it alone
        return text
    try:
        toks = _MD.parseInline(text)
    except Exception:
        return text
    return _finish("".join(_inline_text(t) for t in toks))


def _inline_text(tok):
    """Render one inline token's children to plain text, dropping the delimiters."""
    out = []
    for t in (tok.children or []):
        if t.type == "text":
            out.append(t.content)
        elif t.type == "code_inline":
            out.append(t.content)                     # verbatim: the parser vouched for it
        elif t.type in ("softbreak", "hardbreak"):
            out.append(" ")
        elif t.type == "image":                       # keep the alt text
            out.append("".join(c.content for c in (t.children or [])))
        # link_open/close, em/strong/s open/close, html_inline: delimiters, dropped
    return "".join(out)


def _finish(s):
    return _WS.sub(" ", _ORPHAN_EDGE.sub("", s.strip())).strip()


def plain_block(text):
    """Strip BOTH block-level and inline markdown.

    `plain()` runs the INLINE parser, so block syntax passes through untouched — a
    standalone `## Purpose` stays `## Purpose`. This parses the string as a small
    document instead, so heading hashes, list bullets and fence markers are consumed as
    block structure and never reach the output:

        '## Purpose'                -> 'Purpose'
        '- **Simplicity First**: …' -> 'Simplicity First: …'
        '```py\\nx = 1\\n```'         -> 'x = 1'

    Use it when the input is a clause standing on its own. Inside a document the block
    layer has already been handled by the grammar, and `plain()` is the right call."""
    # NB: no clean() here. Collapsing whitespace first would destroy the newlines that
    # define block structure — a fence would stop being a fence. Whitespace is collapsed
    # at the END instead, once the block layer has been consumed.
    text = (text or "").strip()
    if not text:
        return ""
    if _MD is None:
        return clean(text)
    try:
        toks = _MD.parse(text)
    except Exception:
        return plain(text)
    parts = []
    for t in toks:
        if t.type == "inline":
            parts.append(_inline_text(t))
        elif t.type in ("fence", "code_block"):
            parts.append(t.content)                   # the code, without its fence
    return _finish(" ".join(p for p in parts if p.strip()))


def nl_rules(file_row, types=NL_TYPES, grammar=None, min_words=1, strip_markdown=False):
    """The natural-language rule text of one file, in document order."""
    content = file_row.get(FILES_TEXT_COLUMN) or ""
    render = plain if strip_markdown else clean
    out = []
    for u in segment(content, grammar or GRAMMAR):
        if u["type"] not in types:
            continue
        t = render(u["text"])
        if strip_markdown and u["type"] in ("table_row", "table_header"):
            t = _TABLE_PIPE.sub(" | ", t).strip(" |")   # cell separators are markup too
        if t and len(t.split()) >= min_words:
            out.append(t)
    return out


def export(file_rows, types=NL_TYPES, grammar=None, min_words=1, dedup=False,
           strip_markdown=False):
    """Flatten a corpus to a list of NL rule strings."""
    out, seen = [], set()
    for r in file_rows:
        if skip_reason(r):
            continue
        for t in nl_rules(r, types, grammar, min_words, strip_markdown):
            if dedup:
                k = t.lower()
                if k in seen:
                    continue
                seen.add(k)
            out.append(t)
    return out


def main():
    ap = argparse.ArgumentParser(description="export only the NL rule text as JSON")
    ap.add_argument("-o", "--out", default="-", help="output path ('-' for stdout)")
    ap.add_argument("--files-parquet", default=None, help="local parquet of rule files")
    ap.add_argument("--repo", default=None, help="HF dataset to read instead")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--grammar", default=None)
    ap.add_argument("--include", default="", help="extra unit types, e.g. field,table_row")
    ap.add_argument("--min-words", type=int, default=1, help="drop fragments shorter than this")
    ap.add_argument("--dedup", action="store_true", help="collapse repeated wordings")
    ap.add_argument("--plain", action="store_true",
                    help="strip markdown markup via the inline parser (**bold**, `code`, links)")
    ap.add_argument("--indent", type=int, default=2)
    args = ap.parse_args()

    from .hub import read_files
    table = read_files(args.repo, limit=args.limit, local=args.files_parquet)
    rows = [r for b in table.to_batches(max_chunksize=64) for r in b.to_pylist()]

    types = tuple(NL_TYPES) + tuple(t.strip() for t in args.include.split(",") if t.strip())
    data = export(rows, types, args.grammar, args.min_words, args.dedup, args.plain)

    text = json.dumps(data, indent=args.indent, ensure_ascii=False)
    if args.out == "-":
        sys.stdout.write(text + "\n")
    else:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"{len(data)} NL rules → {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
