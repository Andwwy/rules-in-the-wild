"""The grammar — deterministic segmentation of a rule file into clauses.

This is the whole point of the project, and the only module that decides where one
clause ends and the next begins. It is self-contained by design (no imports from the
annotator or the crawler) and completely deterministic: the same bytes in always produce
the same clauses out, with the same offsets. No model, no heuristic scoring, no I/O.

    segment(text)             -> [{idx, type, char_start, char_end, text}]
    heading_spans(text)       -> [(char_start, level, title)]
    heading_path_at(...)      -> "Usage > Testing"

Two grammars are implemented. `v2` is the default; `v1` reproduces the original
line-splitting segmenter byte-for-byte so previously-cut corpora stay reproducible.
See GRAMMAR.md for the full write-up of the rules below.

v2 unit types
    heading       an ATX or setext heading — structure, never a clause on its own
    code          a fenced or indented code block, kept atomic
    table_header  the first row of a table (the column names)
    table_row     one body row of a table — kept for losslessness, flagged structural
    field         one leaf of YAML front matter (a single-line field, one list item of
                  a multi-line field, or one sentence of a block scalar)
    statement     a paragraph or list item that is a single sentence, kept whole
    clause        one sentence of a paragraph that split into several
    lead_in       a unit ending in ':' (ASCII or fullwidth) — announces the following
                  block (list, code, table); no content of its own; flagged structural
    markup        HTML comments and lone XML/HTML tag lines — renderer plumbing,
                  flagged structural
    field_meta    a front-matter leaf that is machine metadata, not natural language
                  (`model: sonnet`, a `- Read` tool entry); flagged structural

v1 unit types (legacy)
    block         heading / fence / whole table
    prose         a paragraph or list item that did not split
    clause        one piece of a paragraph that did
"""
import bisect
import re

# markdown-it supplies the block skeleton. Guarded so a missing dependency degrades to a
# pure-regex splitter rather than breaking the pipeline.
try:
    from markdown_it import MarkdownIt
    _MD = MarkdownIt("default")
except Exception:                                            # pragma: no cover
    _MD = None

GRAMMARS = ("v1", "v2")
DEFAULT_GRAMMAR = "v2"

# Structural unit types — these carry document skeleton, not directives. Consumers that
# want "just the prose" filter these out; they are kept so the segmentation is lossless.
# `table_row` is here because a row is tabular reference data (command tables, option
# matrices), not a written rule; `lead_in` because a span ending in ':' announces the
# block after it and says nothing on its own — assigning an enforcer to one produces a
# confidently-wrong row downstream.
STRUCTURAL_TYPES = frozenset({"heading", "code", "table_header", "table_row",
                              "lead_in", "markup", "field_meta", "block"})

# A unit must contain at least this many alphanumeric characters to be emitted at all.
# Below it you get punctuation debris ("|---|", "###") rather than text.
_MIN_ALNUM = 3

# ── sentence-terminal protection ──────────────────────────────────────────────────────
# A '.' inside any of these is not a sentence end. Each pattern's matched span is blanked
# out (offset-preserving) before terminals are scanned, so "e.g. foo" never splits.
_ABBR = (r"e\.g|i\.e|etc|vs|cf|approx|resp|incl|Dr|Mr|Ms|Mrs|Prof|Fig|Ex|No|al|Inc|Ltd|"
         r"max|min|std|env|src|dir|repo|impl|config|param|arg|func|var|const|def|obj|str|int|bool")
_PROTECTED = (
    re.compile(r"`[^`\n]*`"),                                  # `foo.bar; baz` — code span
    re.compile(r"\[[^\]]*\]\([^)]*\)"),                        # [text](a.b/c.d) — md link
    re.compile(rf"\b(?:{_ABBR})\.", re.IGNORECASE),            # e.g.  i.e.  etc.
    re.compile(r"\b\d+(?:\.\d+)+"),                            # 1.5.2 — version / decimal
    re.compile(r"\b[\w-]+\.(?:md|mdc|ts|tsx|js|jsx|mjs|cjs|py|rs|go|java|rb|sh|bash|zsh|"
               r"json|jsonc|ya?ml|toml|ini|cfg|lock|txt|css|scss|html|sql|env)\b", re.IGNORECASE),
    re.compile(r"\.{2,}"),                                     # ... — ellipsis
    re.compile(r"\b[A-Z]\.(?=[A-Z]\.)"),                       # U.S.A. — initialisms
    # `- "What's the plan?" -> get_plan` — a short quoted literal followed by more
    # content on the same line; the terminal inside must not cut the mapping in half.
    # A quote that ends its line is left alone so per-line quoted-rule files still split.
    re.compile(r"\"[^\"\n]{1,120}\"(?=[^\n]*\S)"),
    # `(clear? user-facing? migration notes?)` — terminals inside short paren groups
    re.compile(r"\([^()]{1,200}\)"),
    # `2. **Before calling…` / `- "  4. Present…` — a line-start enumerator is a list
    # marker, not a sentence end; splitting after the dot glues "4." to the prior piece
    re.compile(r"(?m)^[ \t>]*(?:[-*+][ \t]+)?[\"'*_]{0,3}(?:\d{1,3}|[A-Za-z])\.(?=[ \t])"),
    re.compile(r"<!--[\s\S]{2,400}?-->"),                      # HTML comments, kept whole
)

_ATX = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
# A paragraph that is one fully-bold line whose text ends without terminal punctuation
# ("**Tech Stack**"), or an `=== PRE-FLIGHT ===` divider — an unmarked section label.
_BOLD_LABEL = re.compile(r"^(?:\*\*|__)[^*_\n]{0,79}[^*_\n.!?。！？:：…](?:\*\*|__)$")
_RULE_LINE = re.compile(r"^={2,}[^=\n]{1,60}={2,}$")
_TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")
_FIELD = re.compile(r"^[A-Za-z_][\w-]*\s*:")
_DASH_ITEM = re.compile(r"^\s*-(?:\s|$)")                      # a YAML sequence entry
_SCALAR_HEADER = re.compile(r"^[|>][0-9+-]{0,2}\s*(?:#.*)?$")  # `|`, `>-`, `|2+` …


def _line_offsets(text):
    """Absolute char offset of the start of every line (index i = line i, 0-based)."""
    offs, pos = [0], 0
    for ln in text.split("\n"):
        pos += len(ln) + 1
        offs.append(pos)
    return offs


def _mask(seg):
    """`seg` with every protected region replaced by NULs. Same length, so offsets found
    in the mask are valid in the original — that is the whole trick."""
    buf = None
    for pat in _PROTECTED:
        for m in pat.finditer(seg):
            if buf is None:
                buf = list(seg)
            for i in range(m.start(), m.end()):
                buf[i] = "\x00"
    return seg if buf is None else "".join(buf)


def _trim(text, a, b):
    """Shrink [a,b) past leading/trailing whitespace. Returns None if nothing is left or
    the span is punctuation debris."""
    piece = text[a:b]
    cs = a + (len(piece) - len(piece.lstrip()))
    ce = b - (len(piece) - len(piece.rstrip()))
    if ce <= cs or sum(ch.isalnum() for ch in text[cs:ce]) < _MIN_ALNUM:
        return None
    return cs, ce


# ── v2: sentence splitting ────────────────────────────────────────────────────────────

def _sentences_v2(text, a, b):
    """Split the inline span [a,b) into sentences.

    Boundaries: a blank line, a sentence terminal (. ! ? and the CJK 。！？；)
    followed by whitespace or the end (the terminal keeps its trailing closers —
    quotes, brackets, emphasis — so `met.)_` and `unannounced.**` end cleanly), a
    semicolon followed by whitespace, a line ending in a colon (a lead-in label),
    and a line starting with a bold `**Label**:` (consecutive label lines used to
    merge into one blob). A PLAIN NEWLINE IS NOT A BOUNDARY — that is the single
    most important difference from v1, because these files are hard wrapped and v1
    cut every wrapped line into its own unit."""
    seg = text[a:b]
    mask = _mask(seg)
    bounds = {0, len(seg)}
    for m in re.finditer(r"\n[ \t]*\n", seg):                  # paragraph break
        bounds.add(m.end())
    for m in re.finditer(r"[.!?]+[\"'»”’)\]}*_]*(?=\s|$)", mask):   # terminal + closers
        bounds.add(m.end())
    for m in re.finditer(r"[。！？；]+[”’」』)\]*_]*", mask):      # CJK terminal (no space after)
        bounds.add(m.end())
    for m in re.finditer(r"[:：][*_]{0,3}(?=\r?\n)", mask):     # lead-in label line end
        bounds.add(m.end())
    for m in re.finditer(r"(?<=[a-z])#(?=\r?\n)", mask):       # `Dates and timestamps#`
        bounds.add(m.end())
    for m in re.finditer(r"\n(?=\*\*[^*\n]{1,60}(?:\*\*[ \t]*:|:\*\*))", seg):
        bounds.add(m.start() + 1)                              # bold-label line start
    # A semicolon separates two directives ("Do A; do B") but also joins noun lists
    # ("lint-only; API fixes; cross-boundary apply"), which shred into fragments if
    # every ';' splits. Split only when BOTH sides carry >=4 words (within the
    # neighboring boundaries/semicolons) and the next part starts with a letter.
    semis = list(re.finditer(r";(?=\s)", mask))
    if semis:
        hard = sorted(bounds)
        spots = [m.start() for m in semis]
        for i, m in enumerate(semis):
            p = m.start()
            j = bisect.bisect_right(hard, p)
            ls = hard[j - 1] if j else 0
            rend = hard[j] if j < len(hard) else len(seg)
            if i > 0 and semis[i - 1].end() > ls:
                ls = semis[i - 1].end()
            if i + 1 < len(semis) and spots[i + 1] < rend:
                rend = spots[i + 1]
            left = [w for w in seg[ls:p].split() if any(c.isalnum() for c in w)]
            right_txt = seg[m.end():rend].lstrip()
            right = [w for w in seg[m.end():rend].split() if any(c.isalnum() for c in w)]
            if len(left) >= 4 and len(right) >= 4 and right_txt[:1].isalpha():
                bounds.add(m.end())
    out = []
    ordered = sorted(bounds)
    for s0, e0 in zip(ordered, ordered[1:]):
        span = _trim(text, a + s0, a + e0)
        if span:
            out.append(span)
    return out


def _field_leaves(text, a, b, depth=0):
    """Leaf spans of one front-matter field span [a,b) (key line first).

    A single-line field is one leaf, as before. A multi-line value used to be folded
    into one opaque unit, which is how a 900-char `instructions:` list became a single
    clause carrying seven rules. Instead: each `- ` sequence entry becomes its own
    leaf (sentence-split if it holds several sentences), a nested map recurses one
    sub-field at a time, and a block scalar (`|`, `>`, plain or quoted) is
    sentence-split — `description: |` holds prose as often as `>` does, and a shell
    script under `hooks: |` has no terminals to split on anyway."""
    seg = text[a:b]
    if "\n" not in seg:
        # single line — but a one-line `description: "Use when … <example>…"` can hold
        # dozens of sentences, the same under-split as a folded block. Literal `\n`
        # escapes inside the value are the YAML encoding of real line breaks (the
        # claude agent-file style), so they bound leaves the same way newlines would.
        outs, prev = [], a
        for m in re.finditer(r"(?:\\[nrt])+", seg):
            if a + m.start() > prev:
                outs.extend(_sentences_v2(text, prev, a + m.start()))
            prev = a + m.end()
        if prev < b:
            outs.extend(_sentences_v2(text, prev, b))
        return outs or [(a, b)]
    if depth >= 4:
        return [(a, b)]
    lines, pos = [], a
    for ln in seg.split("\n"):
        lines.append((pos, pos + len(ln), ln))
        pos += len(ln) + 1
    key_start, key_end, key_line = lines[0]
    body = [l for l in lines[1:] if l[2].strip()]
    if not body:
        return [(a, b)]

    stripped = key_line.strip()
    m = _FIELD.match(stripped)                                 # nested keys are indented
    rest = stripped[m.end():].strip() if m else stripped
    min_ind = min(len(t) - len(t.lstrip()) for _, _, t in body)

    def _starts_chunk(t):                                      # top-level item or sub-key
        return (len(t) - len(t.lstrip())) == min_ind and \
               bool(_DASH_ITEM.match(t) or _FIELD.match(t.strip()))

    chunks, cur = [], None                                     # [start, end, is_subfield]
    for s, e, t in body:
        if cur is None or _starts_chunk(t):
            if cur:
                chunks.append(cur)
            cur = [s, e, bool((len(t) - len(t.lstrip())) == min_ind
                              and _FIELD.match(t.strip()))]
        else:
            cur[1] = e
    chunks.append(cur)

    structured = any(_starts_chunk(t) for _, _, t in body)
    leaves = []
    if not structured:
        # prose scalar: keep a contentful key line attached so `description: Use when`
        # flows into its continuation instead of being cut mid-sentence
        start = key_start if rest and not _SCALAR_HEADER.match(rest) else body[0][0]
        return list(_sentences_v2(text, start, b))
    if not (rest and _SCALAR_HEADER.match(rest)):
        leaves.append((key_start, key_end))                    # bare `key:` → lead_in
    # (`key: |` / `key: >-` is skipped: the indicator carries no content and, unlike a
    # bare `key:`, does not even end in a colon, so it would linger as a field fragment)
    for s, e, sub in chunks:
        if sub:
            leaves.extend(_field_leaves(text, s, e, depth + 1))
        else:
            leaves.extend(_sentences_v2(text, s, e))
    return leaves


def _front_matter_fields(text):
    """Split leading YAML front matter into leaf units, one per field — or, for a
    multi-line field, one per list item / sentence (see `_field_leaves`).

    Front matter is where a skill file states WHEN IT APPLIES (`description: Use when
    …`), which is a rule about the rules. v1 emitted the whole block as one opaque unit.
    Returns (units, end_offset); end_offset is 0 when there is no front matter."""
    if not text.startswith("---\n"):
        return [], 0
    close = re.search(r"\n---[ \t]*(?:\n|$)", text[3:])
    if not close:
        return [], 0
    body_start, body_end = 4, 3 + close.start() + 1
    block_end = 3 + close.end()
    out, cur, pos = [], None, body_start
    for line in text[body_start:body_end].split("\n"):
        if line.strip().startswith("#"):                       # YAML comment — not content
            pass
        elif _FIELD.match(line):                               # a new top-level field
            if cur:
                out.append(cur)
            cur = [pos, pos + len(line)]
        elif cur and line.strip():                             # a continuation line
            cur[1] = pos + len(line)
        pos += len(line) + 1
    if cur:
        out.append(cur)
    units = []
    for a, b in out:
        for la, lb in _field_leaves(text, a, b):
            span = _trim(text, la, lb)
            if span:
                units.append(("field", span[0], span[1]))
    return units, block_end


def _lead_in(text, b):
    """True if the span ending at b is a lead-in: its last real character (allowing
    trailing emphasis markers and quotes) is a colon — ASCII or fullwidth.
    `Structure answers as follows:` announces the list, code block, or table after
    it and carries no directive of its own."""
    i = b - 1
    while i >= 0 and text[i] in "*_ \t\r\"'":
        i -= 1
    return i >= 0 and text[i] in ":："


# A unit that is nothing but markup plumbing: HTML comments, a lone XML/HTML tag line
# (`<plan_template>`, `</Execution_Policy>`), or a one-line tag-wrapped template slot
# (`<arguments> $ARGUMENTS </arguments>`). Content to the renderer, noise to a rule set.
_MARKUP_UNIT = re.compile(
    r"^(?:(?:<!--[\s\S]*?-->"
    r"|<([A-Za-z][\w:.-]*)(?:\s[^<>\n]*?)?>[^<>\n]*</\1>"
    r"|</?[A-Za-z][\w:.-]*(?:\s[^<>\n]*?)?/?>)\s*)+$")


_KEYVAL = re.compile(r"^[A-Za-z_][\w-]*\s*:\s*(.*)$", re.DOTALL)
_LIST_MARKER = re.compile(r"^\s*[-*+]\s+")


def _is_meta_field(text):
    """True for a front-matter leaf that is machine metadata rather than natural
    language: `model: sonnet`, `version: "1.0"`, a `- Read` tool-list entry, a bare
    tag. The test is deterministic: a `key: value` leaf whose value carries fewer
    than 4 words is metadata; a keyless leaf under 4 words without any sentence
    terminal is a bare token. `description: Use when refactoring components` and
    list-item instructions ("Do A strictly.") stay natural language."""
    t = _LIST_MARKER.sub("", text.strip())
    m = _KEYVAL.match(t)
    val = m.group(1) if m else t
    words = [w for w in val.split() if any(c.isalnum() for c in w)]
    if len(words) >= 4:
        return False
    if not m and any(c in val for c in ".!?。！？"):           # a short sentence is NL
        return False
    return True


def _retype_v2(text, raw):
    """Post-pass over v2 units: colon-terminated content units become `lead_in`,
    pure-markup units become `markup`, and non-NL front-matter leaves become
    `field_meta` (all structural). Left as `statement`/`clause`/`field` they read as
    complete rules downstream and get enforcers assigned to fragments that say
    nothing — measured at ~3.5% of a corpus."""
    out = []
    for typ, a, b in raw:
        if typ in ("statement", "clause", "field"):
            if _lead_in(text, b):
                typ = "lead_in"
            elif text[a] == "<" and _MARKUP_UNIT.match(text[a:b]):
                typ = "markup"
            elif typ == "field" and _is_meta_field(text[a:b]):
                typ = "field_meta"
        out.append((typ, a, b))
    return out


def _line_span(offs, m0, m1):
    """(char_start, char_end) for a markdown-it line map, clamped. markdown-it counts
    a bare `\\r` as a line break and `_line_offsets` does not, so a `\\r`-only file
    yields token maps past the end of the table — clamping turns that crash into a
    best-effort span."""
    n = len(offs) - 1
    return offs[min(m0, n)], offs[min(m1, n)]


def _table_rows(text, offs, tmap):
    """One unit per table row. The separator row is dropped and the header is typed
    distinctly. Rows are kept so the segmentation stays lossless, but both row types
    are structural now (see STRUCTURAL_TYPES): a table carries reference data, not
    written rules, and is excluded from the clause stream downstream."""
    out, first = [], True
    for ln in range(tmap[0], min(tmap[1], len(offs) - 1)):
        a, b = offs[ln], offs[ln + 1] - 1
        line = text[a:b]
        if not line.strip() or _TABLE_SEP.match(line):
            continue
        span = _trim(text, a, b)
        if span:
            out.append(("table_header" if first else "table_row", span[0], span[1]))
            first = False
    return out


def _segment_v2(text):
    offs = _line_offsets(text)
    raw, fm_end = [], 0
    fm, fm_end = _front_matter_fields(text)
    raw.extend(fm)

    if _MD is None:                                            # degraded mode
        for a, b in _sentences_v2(text, fm_end, len(text)):
            raw.append(("statement", a, b))
        return _retype_v2(text, raw)

    stack, table_depth, tmap, list_depth = [], 0, None, 0
    for t in _MD.parse(text):
        # markdown-it does not know front matter; whatever it makes of those lines
        # (thematic breaks, indented code) is already emitted as field leaves
        if t.map and offs[min(t.map[0], len(offs) - 1)] < fm_end:
            continue
        if t.type == "table_open" and t.map:
            if table_depth == 0:
                tmap = t.map
            table_depth += 1
            continue
        if t.type == "table_close":
            if table_depth:                                    # open may sit in front matter
                table_depth -= 1
            if table_depth == 0 and tmap:
                raw.extend(_table_rows(text, offs, tmap))
                tmap = None
            continue
        if table_depth:
            continue                                           # rows handled above
        if t.type in ("fence", "code_block") and t.map:
            span = _trim(text, *_line_span(offs, t.map[0], t.map[1]))
            if span:
                raw.append(("code", span[0], span[1]))
            continue
        if t.type == "list_item_open":
            list_depth += 1
        elif t.type == "list_item_close":
            list_depth = max(0, list_depth - 1)
        if t.type.endswith("_open") and t.map:
            stack.append((t.type, t.map))
        elif t.type == "inline" and stack:
            btype, bmap = stack[-1]
            a, b = _line_span(offs, bmap[0], bmap[1])
            if a < fm_end:
                continue                                       # already emitted as fields
            span = _trim(text, a, b)
            if not span:
                continue
            a, b = span
            if btype == "heading_open":
                raw.append(("heading", a, b))
            else:
                pieces = _sentences_v2(text, a, b)
                # A standalone paragraph that is one all-bold line without terminal
                # punctuation ("**Tech Stack**") or an `=== DIVIDER ===` line is a
                # section label the author didn't mark up — a heading, not a rule.
                # Inside a list the same shape ("**Review SLOs regularly**") is
                # usually a real directive, so list items are exempt.
                if len(pieces) == 1 and not list_depth:
                    pa, pb = pieces[0]
                    ptxt = text[pa:pb]
                    if "\n" not in ptxt and (_BOLD_LABEL.match(ptxt) or _RULE_LINE.match(ptxt)):
                        raw.append(("heading", pa, pb))
                        continue
                typ = "statement" if len(pieces) <= 1 else "clause"
                for cs, ce in pieces:
                    raw.append((typ, cs, ce))
    return _retype_v2(text, raw)


# ── v1: the legacy line-splitting grammar (kept byte-compatible) ──────────────────────

def _pieces_v1(text, a, b):
    """v1's splitter: EVERY newline is a boundary, plus [.!?;] before whitespace. A colon
    is deliberately not a boundary ("Name: directive" stays one unit). Retained verbatim
    so v1 output remains reproducible — do not 'fix' it here; fix it in v2."""
    seg = text[a:b]
    bounds = {0, len(seg)}
    for m in re.finditer(r"\n", seg):
        bounds.add(m.end())
    for m in re.finditer(r"[.!?;](?=\s)", seg):
        bounds.add(m.end())
    out = []
    ordered = sorted(bounds)
    for s0, e0 in zip(ordered, ordered[1:]):
        span = _trim(text, a + s0, a + e0)
        if span:
            out.append(span)
    return out


def _segment_v1(text):
    raw = []
    if _MD is not None:
        try:
            offs = _line_offsets(text)
            stack, in_table = [], 0
            for t in _MD.parse(text):
                if t.type == "table_open" and t.map:
                    raw.append(("block", offs[t.map[0]], offs[t.map[1]])); in_table += 1; continue
                if t.type == "table_close":
                    if in_table: in_table -= 1
                    continue
                if in_table:
                    continue
                if t.type in ("fence", "code_block") and t.map:
                    raw.append(("block", offs[t.map[0]], offs[t.map[1]])); continue
                if t.type.endswith("_open") and t.map:
                    stack.append((t.type, t.map))
                elif t.type == "inline" and stack:
                    btype, bmap = stack[-1]
                    a, b = offs[bmap[0]], offs[bmap[1]]
                    seg = text[a:b]
                    a += len(seg) - len(seg.lstrip()); b -= len(seg) - len(seg.rstrip())
                    if b <= a:
                        continue
                    if btype == "heading_open":
                        raw.append(("block", a, b))
                    else:
                        ps = _pieces_v1(text, a, b)
                        typ = "prose" if len(ps) <= 1 else "clause"
                        for cs, ce in ps:
                            raw.append((typ, cs, ce))
        except Exception:
            raw = []
    if not raw:
        for cs, ce in _pieces_v1(text, 0, len(text)):
            raw.append(("prose", cs, ce))
    return raw


# ── public API ────────────────────────────────────────────────────────────────────────

def segment(content, grammar=DEFAULT_GRAMMAR):
    """Segment a rule file into clauses. Returns units in document order, each with exact
    character offsets: `unit["text"] == content[unit["char_start"]:unit["char_end"]]`.

    Overlapping proposals are impossible by construction; identical spans are deduped."""
    if grammar not in GRAMMARS:
        raise ValueError(f"unknown grammar '{grammar}' (expected one of {', '.join(GRAMMARS)})")
    text = content or ""
    if not text.strip():
        return []
    raw = _segment_v1(text) if grammar == "v1" else _segment_v2(text)
    raw.sort(key=lambda r: (r[1], r[2]))
    units, seen = [], set()
    for typ, a, b in raw:
        if (a, b) in seen:
            continue
        seen.add((a, b))
        units.append({"idx": len(units) + 1, "type": typ,
                      "char_start": a, "char_end": b, "text": text[a:b]})
    return units


def heading_spans(content):
    """[(char_start, level, title)] for every ATX heading, skipping fenced code so a
    `# comment` inside a bash block is not mistaken for a section."""
    out, pos, fence = [], 0, None
    for ln in (content or "").split("\n"):
        f = _FENCE.match(ln)
        if f:
            marker = f.group(1)
            if fence is None:
                fence = marker
            elif ln.strip().startswith(fence):
                fence = None
        elif fence is None:
            m = _ATX.match(ln)
            if m:
                out.append((pos, len(m.group(1)), m.group(2).strip()))
        pos += len(ln) + 1
    return out


def heading_path_at(headings, offset, self_is_heading=False):
    """Breadcrumb of the headings enclosing `offset`, e.g. "Usage > Testing".

    A heading is scoped by its ANCESTORS, not itself: `## Testing` under `# Usage` gets
    "Usage", while the prose below it gets "Usage > Testing"."""
    stack = []
    for hstart, level, title in headings:
        if hstart > offset:
            break
        if self_is_heading and hstart == offset:
            # The unit IS this heading. Pop its same-or-deeper-level predecessors before
            # stopping — otherwise a preceding SIBLING stays on the stack and is reported
            # as this heading's parent.
            while stack and stack[-1][0] >= level:
                stack.pop()
            break
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
    return " > ".join(t for _, t in stack)


def line_of(line_offsets, offset):
    """1-based line number containing `offset` (binary search over line starts)."""
    lo, hi = 0, len(line_offsets) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if line_offsets[mid] <= offset:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1


__all__ = ["segment", "heading_spans", "heading_path_at", "line_of", "_line_offsets",
           "GRAMMARS", "DEFAULT_GRAMMAR", "STRUCTURAL_TYPES"]
