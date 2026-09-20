# The parsing grammar

How a rule file becomes clauses. This is the whole mechanism — everything else in the
project is plumbing around it.

Implemented in [`clause_extraction/grammar.py`](clause_extraction/grammar.py); the only
entry point is `segment(text, grammar="v2")`.

---

## 1. What a clause is

A **clause** is the smallest span of a rule file that can stand on its own as a
directive, together with the exact character offsets it occupies in the source.

The parser does **not** decide whether a span *is* a rule. That is a judgement, and
judgements are not reproducible. It decides only where one unit ends and the next
begins, and records what each unit structurally *is* (`heading`, `code`, `table_row`,
`statement`, …). Filtering "just the directives" is a downstream concern, done with a
`WHERE unit_type IN (…)`.

Two hard guarantees:

```
clause_text == file_content[char_start:char_end]     # always, byte for byte
segment(x) == segment(x)                             # always, on any machine, forever
```

No model, no network, no clock, no randomness, no locale. The same bytes in produce the
same clauses out, which is what makes clause ids stable and re-runs idempotent.

---

## 2. The mechanism in one picture

```
 rule file text
      │
      ├─►  LAYER 1 — block skeleton  (markdown grammar, via markdown-it)
      │      front matter · headings · code fences · tables · paragraphs · list items
      │      Each block gets a char span. Atomic blocks are emitted as-is.
      │
      └─►  LAYER 2 — sentence split  (applies only to paragraph/list-item text)
             Split at blank lines, sentence terminals, and semicolons.
             NOT at plain newlines. Terminals inside protected regions don't count.
                    │
                    ▼
             units: [{idx, type, char_start, char_end, text}]
```

Layer 1 answers *"what kind of thing is this region of the document?"*. Layer 2 answers
*"how many directives are in this paragraph?"*. Keeping them separate is what stops code
fences and table pipes from being sentence-split into gibberish.

---

## 3. Layer 1 — the block skeleton

markdown-it parses the document into tokens; each carries a line range, which is
converted to character offsets. Six block kinds are recognised.

### 3.1 YAML front matter → one unit per field *leaf* (`field`)

A leading `---` fence is split at each top-level `key:`, and each field's **value** is
then subdivided:

- a single-line value is one leaf (but a long one-line `description: "Use when … "` is
  sentence-split, since it can hold dozens of sentences);
- each `- ` sequence entry is its own leaf, sentence-split if it holds several;
- a nested map recurses one sub-field at a time;
- a block scalar (`|`, `>`, plain or quoted) is sentence-split — `description: |` holds
  prose as often as `>` does, and a shell script under `hooks: |` has no sentence
  terminals to split on anyway;
- a bare `key:` line whose value follows below is typed `lead_in` (structural, §4.4).

```yaml
---
name: browser-e2e-tests
instructions:
  - Generate SAD strictly from inputs in project-context; do not invent requirements.
  - For MVP scope, prioritize minimal viable views.
---
```
→ `name:` field, `instructions:` lead-in, and one `field` leaf per list item. Folding a
multi-line value into one opaque unit (what happened before 2.1.0) produced 900-char
"clauses" carrying seven rules each — undetectable downstream except by length.

### 3.2 Headings → `heading`

ATX (`## Title`) and setext (`Title\n---`) both. A heading is document skeleton, never a
directive on its own, but it is kept because it scopes everything under it (see §5).

### 3.3 Code fences and indented code → `code`

Emitted whole, never split. A fence is the *example*; the rule is the prose around it.
Splitting `foo.bar(); baz()` at the `;` and `.` would produce nothing but noise.

### 3.4 Tables → one unit per row (`table_header`, `table_row`) — both structural

The separator row (`|---|---|`) is dropped. The first row is typed `table_header`; the
rest are `table_row`. Rows are still emitted (the segmentation stays lossless, and 88
v1 blobs became 483 addressable rows on the test corpus), but **both types are
structural as of 2.1.0**: a row is tabular reference data — command tables, option
matrices — not a written rule, so tables are excluded from the default clause stream.

### 3.5 Paragraphs and list items → handed to Layer 2

The block's span is trimmed of surrounding whitespace and passed to the sentence
splitter. A list item is a block in its own right, so `- Never use X.` is never merged
with its neighbours.

### 3.6 Everything else

Blockquote and list containers are transparent — their inner paragraphs are what get
emitted. Any span with fewer than **3 alphanumeric characters** is dropped, which is what
keeps `###`, `|---|` and stray punctuation out of the output.

---

## 4. Layer 2 — sentence splitting

Applied only to paragraph and list-item text.

### 4.1 Boundaries

A split occurs at:

| boundary | pattern | rationale |
|---|---|---|
| blank line | `\n[ \t]*\n` | a paragraph break is always a hard break |
| sentence terminal | `[.!?]+` plus any trailing closers (quotes, brackets, `**`), then whitespace/end | the closers stay with their sentence — `unannounced.**` and `met.)_` end cleanly |
| CJK terminal | `[。！？；]+` plus closers, no following space required | CJK does not space after terminals; without this, multi-sentence CJK paragraphs never split |
| clause separator | `;` followed by whitespace, only when both sides carry ≥4 words and the next part starts with a letter | "Do A; do B" splits; a noun list ("lint-only; API fixes; cross-boundary apply") stays whole |
| lead-in line end | `:` or `：` (optionally inside `**`) at end of line | `**Common Mistake:**⏎Rigidly enforcing…` is a label plus content, not one thought |
| bold-label line start | a line beginning `**Label**:` / `**Label:**` | consecutive `**Symptoms**:/**Detection**:/**Fix**:` lines used to merge into one blob |
| trailing `#` | `#` preceded by a lowercase letter at end of line | scraped-docs heading style (`Dates and timestamps#`); the lowercase guard spares `C#`/`F#` |

**A plain newline is not a boundary.** This is the single most consequential rule in the
grammar. These files are hard-wrapped at 80–100 columns, so treating `\n` as a boundary
(what v1 did) shreds every wrapped sentence:

```
SOURCE
  **Let components own their spacing.** `Form`, `List`, and `Stack` each control their own padding and
  spacing — don't wrap them in a padded viewport or sprinkle `p-*`/`space-*` around them; that double-pads
  and fights their internal rhythm.

v1  →  '**Let components own their spacing.** `Form`, `List`, and `Stack` each control their own padding and'
       "spacing — don't wrap them in a padded viewport or sprinkle `p-*`/`space-*` around them;"
       'that double-pads'
       'and fights their internal rhythm.'

v2  →  "**Let components own their spacing.** `Form`, `List`, and `Stack` each control their own padding and
        spacing — don't wrap them in a padded viewport or sprinkle `p-*`/`space-*` around them;"
       'that double-pads and fights their internal rhythm.'
```

A colon is **not** a boundary either: `Name: directive` is one unit, because the colon is
a label separator, not a sentence end.

### 4.2 Protected regions — the masking trick

Before terminals are scanned, protected regions are blanked out with NULs in a
**length-preserving copy** of the text. Offsets found in the mask are therefore valid in
the original, and a `.` inside a protected region simply cannot be seen.

| protected | example | would otherwise split as |
|---|---|---|
| code spans | `` `foo.bar; baz` `` | `` `foo. `` + `bar; ` + `baz` `` |
| markdown links | `[guide](../a.md#L2)` | `[guide](../a.` + `md#L2)` |
| abbreviations | `e.g.` `i.e.` `etc.` `vs.` | `…e.g.` + `foo` |
| versions / decimals | `1.5.2` | `1.` + `5.` + `2` |
| filenames | `package.json` `SKILL.md` | `package.` + `json` |
| ellipses | `...` | three empty splits |
| initialisms | `U.S.A.` | per letter |
| mid-line quoted literals | `- "Create a pay?" -> POST /v2/pay` | `- "Create a pay?` + `" -> POST /v2/pay` |
| short paren groups | `(clear? user-facing? notes?)` | `(clear?` + `user-facing?` + `notes?)` |
| line-start enumerators | `2. **Commands**`, `  a. 原因特定` | `…**2.` + `Commands**…` |
| HTML comments | `<!-- SYNC: … -->` | split at any `.`/`;` inside |

A quoted literal is protected only when more content follows it on the same line — a
quote that ends its line is left alone, so files written as one quoted rule per line
still split per sentence.

The abbreviation list includes the common English ones plus the identifier-like words
that appear unquoted in these files (`config.`, `src.`, `impl.`, `max.`, …).

### 4.3 Typing the result

A block that yields **one** piece is a `statement` (a whole paragraph or list item). A
block that yields **several** produces `clause` units. So `unit_type` tells you whether a
span is a complete thought or a fragment of a longer one.

### 4.4 Lead-ins → `lead_in` (structural)

A unit whose last real character is a colon (trailing `**`/`_` emphasis allowed) is
retyped `lead_in`:

```
Structure answers as follows:        - Store empty array at topic and project level:
```

It announces the list, code block, or table after it and carries no directive of its
own. Left typed as content, ~3.5% of a measured corpus were such fragments — and most
were confidently assigned an enforcer downstream despite saying nothing. `Name:
directive` is unaffected: the colon there is internal, not terminal.

---

## 5. What each unit carries beyond its text

### Heading path

Every unit records the breadcrumb of headings enclosing it: `"Composer Plugins >
Concepts > Operations"`. A directive like *"Never use `any`"* is meaningless without
knowing it sits under *"TypeScript > Types"*.

A heading is scoped by its **ancestors, not itself** — `## Testing` under `# Usage` gets
`"Usage"`, while the prose beneath it gets `"Usage > Testing"`. That keeps a section
title one level above its body instead of self-nesting.

Headings are found by a separate line scan that tracks code fences, so a `# comment`
inside a bash block is never mistaken for a section.

### Offsets

`char_start` / `char_end` are exact and are what an annotation UI anchors to.
`line_start` / `line_end` are 1-based and are what a human reads and what `link#L12`
resolves to. Both are stored because both are needed.

### `is_structural`

True for `heading`, `code`, `table_header`, `table_row` and `lead_in` — the skeleton
plus spans that carry no directive of their own. The default filter for "clauses that
could be directives" is `WHERE NOT is_structural`.

---

## 6. Unit types

| type | what it is | structural |
|---|---|---|
| `statement` | a paragraph or list item that is a single sentence | |
| `clause` | one sentence of a paragraph that split into several | |
| `field` | one leaf of YAML front matter (field, list item, or sentence) | |
| `heading` | an ATX or setext heading | ✓ |
| `code` | a fenced or indented code block | ✓ |
| `table_header` | the column-name row of a table | ✓ |
| `table_row` | one body row of a table — reference data, not a rule | ✓ |
| `lead_in` | a span ending in ':' or '：' that announces the following block | ✓ |
| `markup` | HTML comments and lone XML/HTML tag lines | ✓ |
| `field_meta` | a non-NL front-matter leaf (`model: sonnet`, `- Read`) | ✓ |

Headings also absorb unmarked section labels: a standalone paragraph that is one
fully-bold line without terminal punctuation (`**Tech Stack**`) or an `=== DIVIDER ===`
line is typed `heading`. The same bold shape inside a list item stays a `statement`
(`1. **Review SLOs regularly**` is a directive, not a label).

---

## 7. v1 vs v2

`v1` is the original segmenter, kept **byte-for-byte** so any corpus cut with it stays
reproducible (verified: identical output on all 57 files). Select it with
`--grammar v1`. Do not "fix" v1 — fix v2.

| | v1 | v2 |
|---|---|---|
| newline is a boundary | **yes** | no |
| terminal protection | none | code spans, abbreviations, versions, filenames, links |
| tables | one blob | one unit per row |
| front matter | one blob | one unit per field |
| unit types | `block` / `prose` / `clause` | 7 types + `is_structural` |

Measured over the same 57 files (`--compare`):

```
                                    v1        v2
total units                       4202      4198
mid-sentence breaks                376         0
≤3-word fragments                  451       185
```

A *mid-sentence break* is a unit that does not end in terminal punctuation and is
followed by one starting lowercase — the signature of a sentence cut in half.

---

## 8. Determinism and change control

The parser has no inputs but the text. It does not consult the network, the filesystem,
the clock, a random source, or the locale, and it holds no state between calls.

Because output is a pure function of (text, grammar), every clause row records the
`grammar` and `parser_version` that produced it. Those are part of the
already-extracted key:

```
(file_id, content_sha256, grammar, parser_version)
```

Change the grammar and bump `PARSER_VERSION` in `config.py`, and the runner re-cuts the
whole corpus on the next run, replacing superseded rows rather than accumulating them.
**Any change to segmentation requires a version bump** — otherwise old and new clauses
silently coexist in the same dataset.

Before landing a grammar change, run `--compare` on the corpus. It reports total units,
mid-sentence breaks and fragment counts for both grammars and writes nothing.

---

## 9. Known limits

Honest list of what this grammar does not do well.

- **Fragments remain.** ~185 units of ≤3 words survive — mostly bare paths and
  inline-code stubs (label lines like `Testing:` are now typed `lead_in`). They are real
  spans of the document, so they are kept rather than silently dropped; filter on
  `n_words` if you want them gone.
- **Plain-text label lines are indistinguishable from short statements.** `Product
  Tours` above a bullet list is a section label, but with no bold, colon, or `#` there
  is no deterministic marker; it stays a `statement`.
- **A sentence split inside a quote that spans to end-of-line leaves a stray quote
  char.** `"Sentence one. Sentence two."` yields two complete sentences, the first
  opening and the second closing the quote. `export.plain()` sweeps the orphans.
- **Terminal-less lines inside block scalars still merge** (`Triggers on: x, y⏎Part of
  the Frontend category.`) — a newline is not a boundary and nothing else marks one.
- **Fence-parity misparses.** A document with an unbalanced ``` fence flips code/prose
  for the rest of the file; the grammar inherits markdown-it's reading.
- **A clause can still span a wrapped line.** `clause_text` keeps the source's newlines
  verbatim, because the offsets must round-trip. Normalize whitespace at display time
  (`re.sub(r"\s+", " ", text)`) — `text_sha256` is already computed that way.
- **Nested list items are independent.** `- Parent:` followed by indented children
  yields separate units; the parent's colon does not bind them, but it is now typed
  `lead_in`, so it no longer masquerades as a rule.
- **`\r`-only line endings degrade.** markdown-it counts a bare `\r` as a line break;
  `_line_offsets` does not. Token maps are clamped so such files no longer crash, but
  their segmentation is coarse (typically one unit).
- **Bare `key:` lines above indicator-only scalars are dropped.** For
  `description: >-`, the key line carries no content and is not emitted; the value's
  sentences are, without the field name attached (recoverable via offsets).
- **Non-markdown files get the same treatment.** `.cursorrules` is often plain prose;
  markdown-it parses it as one long paragraph, which is usually right but means a file
  with no markdown structure gets no heading paths.
- **Tables are split by line, not by cell.** A row is one unit even when its cells hold
  several independent facts.
- **Setext headings are not in `heading_spans`.** The line scanner recognises ATX only,
  so a setext-headed section contributes no breadcrumb (it is still emitted as a
  `heading` unit by Layer 1).
