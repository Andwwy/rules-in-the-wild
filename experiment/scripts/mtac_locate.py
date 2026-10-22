"""Where MTAC's checker found each policy violation: the file and line, found black-box (no model calls). A library:
trajectory_viewer.py calls locate() for each failed policy item of a run (cached in <run>/violations.json).
Its earlier command line, for the AgentProbe outputs, is in archive/agentprobe-path-2026-10-19/scripts/.

MTAC's checker scripts return only pass or fail, and their code stays unread (held out). So for every turn and scored
policy rule that MTAC's checker failed (output/script_scores.json), the same checker is run again, through AgentProbe's
own runner, on changed copies of that turn's material (final reply + workspace snapshot):
  - the reply: when an empty reply with no files passes but the reply with no files fails, its lines are searched; when
    a reply of just a word the requirement asks for ("汪～") passes, the reply lacks it, and its first or last line is
    shown (the one where adding the word makes it pass);
  - the files: the fewest files whose removal makes it pass (or, when it fails even with no files, each file that
    fails alone);
  - in such a file, only some of its lines kept (halves, then halves of those): the line that still fails alone is a
    violating line; it is taken out and the search repeats (at most 4 lines per file, 3 files per turn); lines that
    fail only together (a long function) are shown as a block;
  - a file that fails even when empty: if its name or folder decides, the path is shown; if the line the requirement
    asks for, put on top, makes it pass, the file's first lines are shown;
  - a file that passes when any one line is removed is judged on its line count: its last line is shown;
  - a file that fails with any text in it (one line, two lines) is shown as a path; one that also fails empty, and
    that neither its path nor an asked-for line explains, is not located.
In a line that fails alone, the smallest part of it that still fails alone is marked, with any word it cuts made whole
(the "lang=" of `lang="x"`).
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
import paths                                           # noqa: E402

paths.use("agentprobe")
from benchmarks.mtacifbench.models import MTACIFBenchQuestion   # noqa: E402
from benchmarks.mtacifbench.validation import run_validation_code   # noqa: E402

MTAC = paths.MTAC_DATA
SKIP = {"node_modules", ".git", "__pycache__", ".venv", "venv", "site-packages", "dist", "build", ".cache"}
MAX_FILES, MAX_LINES, WIDTH = 3, 4, 160
WORD = re.compile(r"[A-Za-z0-9_$]")


def text_files(root: Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not SKIP & set(p.relative_to(root).parts[:-1]):
            try:
                t = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if "\0" not in t:
                out[str(p.relative_to(root))] = t
    return out


class Checker:
    """MTAC's checker for one item, run on a reply and a workspace given as {path: text}. fails() is True only for a
    clear fail (a crash or a timeout is not a fail)."""

    def __init__(self, code: str, timeout: int):
        self.code, self.timeout = code, timeout

    def fails(self, reply: str, files: dict[str, str]) -> bool:
        with tempfile.TemporaryDirectory(prefix="mtac_locate_") as tmp:
            for rel, text in files.items():
                p = Path(tmp) / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
            return run_validation_code(self.code, reply, Path(tmp), self.timeout, "[locate]") is False


def split(text: str) -> tuple[list[str], bool]:
    lines = text.split("\n")
    end = text.endswith("\n")
    return (lines[:-1] if end else lines), end


def join(lines: list[str], idx: list[int], end: bool) -> str:
    return "\n".join(lines[i] for i in idx) + ("\n" if end and idx else "")


def row(file: str, n: int | None, text: str = "", mark: tuple[int, int] | None = None, note: str | None = None) -> dict:
    """A snippet as the page shows it: segs = [[text, marked 0|1], …], cut to WIDTH around the mark."""
    a, b = mark if mark else (0, 0)
    while mark and 0 < a < len(text) and WORD.match(text[a - 1]) and WORD.match(text[a]):   # whole words
        a -= 1
    while mark and 0 < b < len(text) and WORD.match(text[b - 1]) and WORD.match(text[b]):
        b += 1
    while mark and a > 0 and text[a - 1] in " \t":             # the spaces next to the mark belong to it
        a -= 1
    while mark and b < len(text) and text[b] in " \t":
        b += 1
    lo = max(0, min(a - 40, len(text) - WIDTH)) if len(text) > WIDTH else 0
    hi = min(len(text), lo + WIDTH)
    segs = [["…", 0]] if lo else []
    for t, m in ((text[lo:max(lo, a)], 0), (text[max(lo, a):min(hi, b)], 1), (text[max(lo, b):hi], 0)):
        if t:
            segs.append([t, m])
    if hi < len(text):
        segs.append(["…", 0])
    return {"file": file, "line": n, "segs": segs, "note": note}


def whole(text: str) -> tuple[int, int]:
    return (len(text) - len(text.lstrip()), len(text.rstrip()))


def shrink(fails_on, n: int) -> tuple[int, int]:
    """The smallest window [i, j) of n items that still fails (binary search: first the start, then the end)."""
    lo, hi = 0, n - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        lo, hi = (mid, hi) if fails_on(mid, n) else (lo, mid - 1)
    i, lo, hi = lo, lo + 1, n
    while lo < hi:
        mid = (lo + hi) // 2
        lo, hi = (lo, mid) if fails_on(i, mid) else (mid + 1, hi)
    return i, lo


def narrow(fails_with, lines: list[str], end: bool):
    """The lines that fail alone (keep-only search): [("line", k) | ("lines", first, last)], or "count" when the text is
    judged by its line count (any one line removed makes it pass)."""
    every, found, rest = list(range(len(lines))), [], list(range(len(lines)))
    while len(found) < MAX_LINES and rest and fails_with(join(lines, rest, end)):
        s = rest
        while len(s) > 1:
            a, b = s[: len(s) // 2], s[len(s) // 2:]
            if fails_with(join(lines, a, end)):
                s = a
            elif fails_with(join(lines, b, end)):
                s = b
            else:
                break
        if len(s) != 1:                                        # the lines fail only together (e.g. a long function)
            i, j = shrink(lambda i, j: fails_with(join(lines, s[i:j], end)), len(s))
            found.append(("lines", s[i], s[j - 1]))
            break
        k = s[0]
        if not found and len(lines) > 2 and not fails_with(join(lines, [i for i in every if i != k], end)):
            other = next(i for i in (len(lines) // 2, len(lines) - 1, 0) if i != k)
            if not fails_with(join(lines, [i for i in every if i != other], end)):
                return "count"
        found.append(("line", k))
        rest = [i for i in rest if i != k]
    return found


def line_rows(file: str, lines: list[str], got, fails_text) -> list[dict]:
    """Rows for narrow()'s result; in a line that fails alone, the part that still fails alone is marked."""
    out = []
    for g in got:
        if g[0] == "lines":                                    # every line of the block, at most 6
            out += [row(file, k + 1, lines[k], whole(lines[k]), f"lines {g[1] + 1}–{g[2] + 1}" if k == g[1] else None)
                    for k in range(g[1], min(g[2], g[1] + 5) + 1)]
            continue
        t = lines[g[1]]
        mark = shrink(lambda i, j: fails_text(t[i:j]), len(t)) if t.strip() and fails_text(t) else whole(t)
        out.append(row(file, g[1] + 1, t, mark))
    return out


def asked(req: str) -> list[str]:
    """Text the requirement asks for: its quoted parts and its ASCII runs (e.g. "-*- coding: utf-8 -*-")."""
    found = re.findall(r'["“”「」『』]([^"“”「」『』]{1,160})["“”「」『』]', req) + re.findall(r"[!-~][ -~]{3,}[!-~]", req)
    return list(dict.fromkeys(q.strip() for q in found if q.strip()))


COMMENT = ("{}", "# {}", "// {}", "<!-- {} -->", "/* {} */", "-- {}")


def file_rows(chk: Checker, rp: str, ctx: dict[str, str], f: str, req: str) -> list[dict]:
    """Where file f breaks the rule, in workspace ctx (f's text replaced), with reply rp."""
    text, p = ctx[f], Path(f)

    def ws(t: str, name: str = f) -> dict[str, str]:
        return {**{g: v for g, v in ctx.items() if g != f}, name: t}

    flines, fend = split(text)
    any_text = lambda: chk.fails(rp, ws("a")) and chk.fails(rp, ws("b\nc"))
    if chk.fails(rp, ws("")):                                  # fails even when empty: its path, or content it lacks
        if chk.fails(rp, ws(text, str(p.parent / ("a" + p.suffix)))) != chk.fails(rp, ws(text, str(p.parent / ("ab" + p.suffix)))):
            return [row(f, None, p.name, (0, len(p.name)), f"{len(p.name)} characters")]
        if p.parent != Path(".") and not chk.fails(rp, ws(text, p.name)):
            return [row(f, None, f, (0, len(f)), f"{len(p.parts) - 1} folder levels")]
        for q in asked(req):                                   # the asked-for line put on top makes it pass
            if any(not chk.fails(rp, ws(c.format(q) + "\n" + text)) for c in COMMENT):
                return [row(f, k + 1, flines[k], whole(flines[k]), "start of the file" if k == 0 else None)
                        for k in range(min(3, len(flines)))]
        if any_text():                                         # fails whatever it holds: not located in it
            return []
    elif any_text():                                           # any text in this file fails: the file itself
        return [row(f, None, f, (0, len(f)), "fails with any content")]
    nl = "\n" if fend else ""
    got = narrow(lambda t: chk.fails(rp, ws(t)), flines, fend)
    if got == "count":
        last = flines[-1] if flines else ""
        return [row(f, len(flines), last, whole(last) if last.strip() else None,
                    f"{len(flines)} lines" + (", then a final newline" if fend else ""))]
    return line_rows(f, flines, got, lambda t: chk.fails(rp, ws(t + nl)))


def locate(chk: Checker, req: str, reply: str, files: dict[str, str]) -> list[dict] | None:
    if not chk.fails(reply, files):
        return None                                            # not reproduced
    lines, end = split(reply)
    filled = [k for k, l in enumerate(lines) if l.strip()]
    neutral = not chk.fails("", {})                            # an empty reply with no files passes
    out = []
    if neutral and chk.fails(reply, {}):                       # the reply breaks it: its lines
        got = narrow(lambda t: chk.fails(t, {}), lines, end)
        got = [("line", k) for k in filled] if got == "count" else got
        out += line_rows("reply", lines, got, lambda t: chk.fails(t, {}))[:MAX_LINES]
    if not neutral:
        for q in asked(req):
            if not chk.fails(q, {}):                           # a reply of just the asked-for word passes: it is missing
                if not filled:
                    return []
                start, finish = not chk.fails(q + reply, {}), not chk.fails(reply + q, {})
                ends = ([(filled[0], "start of the reply")] if start or not finish else []) + \
                       ([(filled[-1], "end of the reply")] if finish or not start else [])
                return [row("reply", k + 1, lines[k], whole(lines[k]), note) for k, note in ends]
    rp = "" if neutral else reply
    if not chk.fails(rp, files):
        return out
    if not chk.fails(rp, {}):                                  # the files whose removal makes it pass (fewest)
        bad = list(files)
        for f in list(bad):
            trial = [g for g in bad if g != f]
            if not chk.fails(rp, {g: v for g, v in files.items() if g not in trial}):
                bad = trial
        ctx = lambda f: {g: v for g, v in files.items() if g not in bad or g == f}
    else:                                                      # it fails with no files: each file alone
        bad = [f for f in files if chk.fails(rp, {f: files[f]})]
        ctx = lambda f: {f: files[f]}
    shown = 0
    for f in bad[:MAX_FILES * 3]:                              # up to 3 files where the violation is found
        rows = file_rows(chk, rp, ctx(f), f, req)
        out += rows
        shown += bool(rows)
        if shown == MAX_FILES:
            break
    return out
