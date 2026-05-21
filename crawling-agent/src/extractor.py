"""Markdown → list of (rule_text, line_start, line_end).

Prototype heuristics — good enough for ~80% of cursor/claude/agents files:
    1. Any top-level bulleted list item is a rule.
    2. Any imperative sentence in a numbered list is a rule.
    3. Any line starting with 'MUST', 'NEVER', 'ALWAYS', 'DO NOT' is a rule.

This is intentionally simple. A v0.2 extractor would call a small LLM to
segment prose blocks into rules; the schema doesn't care which extractor
produced a row (rule.extractor_version distinguishes versions later).

Claude marketplace handling (added with the claude_marketplace adapter):
    - YAML frontmatter is stripped before bullet extraction (skill/agent files
      start with `---\\n…\\n---`). If the frontmatter has a `description:`
      single-line scalar, it's emitted as a candidate rule with its real line
      numbers — that's often the only directive a skill carries.
    - For kinds where the body is one instruction (commands), if no bullets /
      numbered items / imperatives match, the trimmed body is emitted as one
      rule. Pass kind="claude_plugin_command" to enable this fallback.
"""

import re
from dataclasses import dataclass


_BULLET_RE = re.compile(r"^\s*[-*+]\s+(.+?)\s*$")
_NUMBERED_RE = re.compile(r"^\s*\d+\.\s+(.+?)\s*$")
_IMPERATIVE_RE = re.compile(r"^\s*(MUST|NEVER|ALWAYS|DO NOT|DON'T)\b.*$", re.IGNORECASE)
_HEADING_RE = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*$")
# Bullets that are pure file references — backtick-or-bare paths with at least
# one slash, no spaces. AGENTS.md files often list "the files this guidance
# applies to" as a bulleted reference list; those aren't rules.
_PATH_LIKE_RE = re.compile(r"^[`A-Za-z0-9_./\-]+$")
# YAML frontmatter delimiter (line of exactly three dashes, optional trailing ws).
_FRONTMATTER_DELIM_RE = re.compile(r"^---\s*$")
# Single-line `description: text` scalar inside frontmatter. Skips block /
# folded forms (`description: |`/`>`); they fall through to body extraction.
_FRONTMATTER_DESCRIPTION_RE = re.compile(r"^description:\s*(?!\||>)(.+?)\s*$")

_SINGLE_RULE_FALLBACK_KINDS = frozenset({"claude_plugin_command"})


@dataclass
class ExtractedRule:
    text: str
    line_start: int      # 1-indexed
    line_end: int
    section_anchor: str | None  # most recent heading


def _strip_frontmatter(lines: list[str]) -> tuple[list[str], int, list[ExtractedRule]]:
    """If the file starts with a YAML frontmatter block, return
    (lines_without_frontmatter, line_offset, candidate_rules). The
    line_offset is the count of removed lines so downstream line numbers stay
    accurate (rule.line_start is 1-indexed against the original file).

    `candidate_rules` contains a single ExtractedRule iff the frontmatter has
    a single-line `description:` field — that's the skill/agent convention.
    """
    if not lines or not _FRONTMATTER_DELIM_RE.match(lines[0]):
        return lines, 0, []
    # Find the closing delimiter. Allow blank lines but bail if missing.
    close_idx = -1
    for idx in range(1, len(lines)):
        if _FRONTMATTER_DELIM_RE.match(lines[idx]):
            close_idx = idx
            break
    if close_idx == -1:
        return lines, 0, []
    candidates: list[ExtractedRule] = []
    for fm_line_idx in range(1, close_idx):
        m = _FRONTMATTER_DESCRIPTION_RE.match(lines[fm_line_idx])
        if not m:
            continue
        text = m.group(1).strip().strip("'\"")
        if len(text) >= 8:
            candidates.append(ExtractedRule(
                text=text,
                line_start=fm_line_idx + 1,
                line_end=fm_line_idx + 1,
                section_anchor="frontmatter",
            ))
        break  # only the first description: counts
    remaining = lines[close_idx + 1:]
    return remaining, close_idx + 1, candidates


def extract(raw: str, kind: str | None = None) -> list[ExtractedRule]:
    lines_all = raw.splitlines()
    lines, line_offset, frontmatter_rules = _strip_frontmatter(lines_all)
    rules: list[ExtractedRule] = list(frontmatter_rules)
    current_heading: str | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if (m := _HEADING_RE.match(line)):
            current_heading = m.group(2).strip()
            i += 1
            continue
        text = None
        if (m := _BULLET_RE.match(line)):
            text = m.group(1)
        elif (m := _NUMBERED_RE.match(line)):
            text = m.group(1)
        elif _IMPERATIVE_RE.match(line):
            text = line.strip()

        if text:
            # Pull continuation lines that are indented (multi-line bullet).
            end = i
            while end + 1 < len(lines) and re.match(r"^\s{2,}\S", lines[end + 1]):
                text = text + " " + lines[end + 1].strip()
                end += 1
            text = text.strip()
            # Filter trivial noise: empty, very short, or pure code/links.
            if (
                len(text) >= 8
                and not text.startswith("```")
                and not (_PATH_LIKE_RE.match(text) and "/" in text)
            ):
                rules.append(ExtractedRule(
                    text=text,
                    line_start=i + 1 + line_offset,
                    line_end=end + 1 + line_offset,
                    section_anchor=current_heading,
                ))
            i = end + 1
        else:
            i += 1

    # Single-rule fallback for files where the whole body IS one instruction.
    # Only fires for kinds in _SINGLE_RULE_FALLBACK_KINDS (e.g. claude_plugin_command)
    # and only when bullet/numbered/imperative extraction produced nothing from
    # the body (frontmatter rules don't count — they live above the body).
    body_rule_count = len(rules) - len(frontmatter_rules)
    if body_rule_count == 0 and kind in _SINGLE_RULE_FALLBACK_KINDS:
        body_text, body_start, body_end = _trim_body(lines, line_offset)
        if body_text and len(body_text) >= 8:
            rules.append(ExtractedRule(
                text=body_text,
                line_start=body_start,
                line_end=body_end,
                section_anchor=None,
            ))
    return rules


def _trim_body(lines: list[str], line_offset: int) -> tuple[str, int, int]:
    """Join non-blank body lines into one rule, returning (text, line_start,
    line_end) in original-file 1-indexed coordinates. Caps at 1500 chars to
    avoid embedding entire command bodies that include code blocks."""
    first = last = -1
    for idx, line in enumerate(lines):
        if line.strip():
            if first == -1:
                first = idx
            last = idx
    if first == -1:
        return "", 0, 0
    joined = " ".join(line.strip() for line in lines[first:last + 1] if line.strip())
    joined = re.sub(r"\s+", " ", joined).strip()
    if len(joined) > 1500:
        joined = joined[:1500].rsplit(" ", 1)[0] + "…"
    return joined, first + 1 + line_offset, last + 1 + line_offset
