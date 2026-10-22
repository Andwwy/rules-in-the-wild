"""Grammar tests: the fence opened at the end of a prose line (2.3.0), adversarial inputs
around it, seeded invariant fuzzing, and the two open defects pinned as xfail.

    python -m pytest tests -q
"""
import random
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from clause_extraction.grammar import (STRUCTURAL_TYPES, _ORPHAN_MAX, _orphan_fences,  # noqa: E402
                                       heading_spans, segment)


def units(text):
    return [(u["type"], u["text"]) for u in segment(text)]


def prose(text):
    return [t for typ, t in units(text) if typ not in STRUCTURAL_TYPES]


# ── a fence opened at the end of a prose line ──────────────────────────────────────────

MTAC = ("请严格遵循以下约束条件：\n"
        "1. 修改代码前把计划写进dev_plan.md。\n"
        "2. 每次更新后更新 Review.md 文件，格式要求如下：```\n"
        "Code Quality Review: [Task]\n"
        "\n"
        "Strengths:\n"
        "- [What's done well]\n"
        "```。\n"
        "3. 生成的代码文件里的文件引用都得是相对路径。\n"
        "4. 所有注释都只使用英文。")


def test_mtac_policy_keeps_every_item():
    assert prose(MTAC) == ["1. 修改代码前把计划写进dev_plan.md。",
                           "2. 每次更新后更新 Review.md 文件，格式要求如下：```",
                           "3. 生成的代码文件里的文件引用都得是相对路径。",
                           "4. 所有注释都只使用英文。"]
    code = [t for typ, t in units(MTAC) if typ == "code"]
    assert code == ["Code Quality Review: [Task]\n\nStrengths:\n- [What's done well]\n```。"]


def test_template_lines_are_not_rules():
    assert not any("[What's done well]" in t for t in prose(MTAC))


@pytest.mark.parametrize("text", [
    "1. Use this format: ```\r\nStrengths: x\r\n```。\r\n2. Second rule here.\r\n",        # CRLF
    "> 1. Use this format: ```\n> Strengths: x\n> ```。\n> 2. Second rule here.\n",      # blockquote
    "1. A format: ~~~\nStrengths: x\n~~~\n2. Second rule here.\n",                       # tildes
    "1. Return JSON like: ```json\n{\"key\": 1}\n```\n2. Second rule here.\n",           # info word
    "1. A format: ```\nxyz\n```.\n2. Second rule here.\n",                               # ASCII punct
])
def test_repaired_variants(text):
    assert _orphan_fences(text)
    assert prose(text)[-1].endswith("2. Second rule here.")


def test_two_orphans():
    text = "1. A format: ```\nxyz\n```。\n2. B format: ```\nuvw\n```。\n3. Third rule here.\n"
    assert len(_orphan_fences(text)) == 2
    assert prose(text) == ["1. A format: ```", "2. B format: ```", "3. Third rule here."]


def test_heading_after_template_is_found():
    text = "1. A format: ```\nxyz\n```。\n\n## Testing\n\nRun the tests.\n"
    assert [h[2] for h in heading_spans(text)] == ["Testing"]


def test_fence_mask_frees_prose_after_template():
    bulk = pytest.importorskip("clause_extraction.bulk")
    lines = MTAC.split("\n")
    mask = bulk._fenced(lines)
    assert [ln for ln, m in zip(lines, mask) if m] == lines[3:8]


# ── adversarial: inputs the repair must leave alone ────────────────────────────────────

@pytest.mark.parametrize("text", [
    # prose that mentions ``` and a genuinely unclosed fence: the closer carries an info word
    "Wrap code samples in ```\n\nSome rule here.\n\n```python\nprint(1)\n",
    # same, closing line with an info word
    "1. A format: ```\nx\n```yaml\nkey: v\n",
    # marker kinds differ
    "1. A format: ~~~\nxyz\n```\n2. Second rule here.\n",
    # opener and closer at different blockquote depth
    "> Format: ```\nUse pnpm, never npm.\n```。\n",
    # more than _ORPHAN_SPAN lines apart
    "1. A format: ```\n" + "line\n" * 70 + "```\n2. Second rule here.\n",
    # opener inside YAML front matter
    "---\nFormat: ~~~\n**Label**:\n---\n~~~。",
    # an even number of runs is an inline span, not an opener
    "1. Use ```x``` here and ```y```\n\n```\nunclosed\n",
    # a balanced document with a prose line ending in ```
    "Wrap code in ```\n\n```bash\nls\n```\n\nRun the tests.\n",
    # opener on the last line, nothing to close
    "1. A format: ```",
])
def test_left_alone(text):
    assert _orphan_fences(text) == []


def test_balanced_document_is_unchanged():
    text = "Use this format: ```\n```bash\nls\n```\nAlways run tests.\n"
    assert _orphan_fences(text) == []
    assert ("code", "```bash\nls\n```") in units(text)


def test_bare_cr_line_endings_do_not_crash():
    segment("1. Use this format: ```\rStrengths:\r```。\r2. Second rule here.\r")


def test_repairs_are_capped():
    text = "".join(f"{k}. Rule {k} format: ```\nStrengths: x{k}\n```。\n" for k in range(1, 3001))
    t0 = time.time()
    assert len(_orphan_fences(text)) == _ORPHAN_MAX
    segment(text)
    assert time.time() - t0 < 5


# ── invariants on seeded random documents ──────────────────────────────────────────────

PARTS = ["# Title", "## Testing", "Use pnpm, never npm.", "1. 必须使用中文回复。", "- Do not edit generated files.",
         "- **Rule**: keep functions short.", "> Note: quoted rule here.", "| a | b |", "|---|---|", "| x | y |",
         "Use this format: ```", "格式要求如下：```", "Return JSON like: ```json", "Wrap code in ```", "Strengths:",
         "- [What's done well]", "```", "```。", "```python", "~~~", "~~~。", "Format: ~~~", "    indented code",
         "print(1)", "", "", "Use ```x``` inline twice ```y```.", "> ```", "> Format: ```", "---", "key: value",
         "e.g. this. And that!", "**Label**:"]


def _docs(n, seed=20261006):
    rng = random.Random(seed)
    for _ in range(n):
        nl = rng.choice(["\n", "\n", "\r\n"])
        doc = nl.join(rng.choice(PARTS) for _ in range(rng.randint(1, 40)))
        yield ("---\nname: x\ndescription: Use when testing.\n---\n" + doc) if rng.random() < .1 else doc


def test_invariants_on_random_documents():
    bulk = pytest.importorskip("clause_extraction.bulk")
    for doc in _docs(3000):
        us = segment(doc)
        assert all(doc[u["char_start"]:u["char_end"]] == u["text"] for u in us)
        assert all(a["char_end"] <= b["char_start"] for a, b in zip(us, us[1:]))
        assert us == segment(doc)
        heading_spans(doc)
        assert len(bulk._fenced(doc.split("\n"))) == len(doc.split("\n"))


# ── open defects, pinned so a fix flips them ───────────────────────────────────────────

@pytest.mark.xfail(strict=True, reason="a directive ending in ':' is typed lead_in and dropped as structural")
def test_directive_ending_in_colon_is_kept():
    text = "Use the provided `recalc.py` script to recalculate formulas:\n\n```bash\npython recalc.py\n```\n"
    assert prose(text) == ["Use the provided `recalc.py` script to recalculate formulas:"]


@pytest.mark.xfail(strict=True, reason="a fence nested in a same-length fence flips code/prose for the rest of the file")
def test_nested_fence_does_not_swallow_later_rules():
    text = ("Use this template:\n\n```markdown\n## Example\n\n```bash\nls\n```\n\nDone.\n```\n\n"
            "Always run the tests before committing.\n")
    assert "Always run the tests before committing." in prose(text)
