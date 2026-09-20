"""Build an NL control set from an ALREADY-SEGMENTED clause dataset.

Input is a JSON array of {id, clause} — someone else's segmentation. The units are
therefore fixed: this script does NOT re-split them, because a control set has to align
1:1 by id with its source. The parser is used for the two jobs it can do without moving
a boundary:

  1. CLASSIFY   run each clause through the grammar and read back what it structurally
                is. Headings, code fences and empty fragments are not NL rule text and
                are dropped, with the reason recorded.
  2. STRIP      render the survivors through the inline parser to remove markdown
                markup (**bold**, `code`, [links](url)) while keeping the wording.

    python make_control_set.py IN.json -o NL-control-set.json
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clause_extraction.export import plain
from clause_extraction.grammar import STRUCTURAL_TYPES, segment


def classify(text):
    """What the grammar makes of a standalone clause: (types, n_units)."""
    units = segment(text or "")
    return [u["type"] for u in units], len(units)


def drop_reason(text):
    """Why this clause is not NL rule text, or None if it is."""
    types, n = classify(text)
    if n == 0:
        return "no parseable content"
    if all(t in STRUCTURAL_TYPES for t in types):
        kinds = sorted(set(types))
        return f"structural ({', '.join(kinds)})"
    return None


def build(items, key="clause", keep_source=False):
    kept, dropped = [], []
    for it in items:
        raw = it.get(key) or ""
        why = drop_reason(raw)
        if why:
            dropped.append({"id": it.get("id"), "reason": why,
                            "clause": raw[:80] + ("…" if len(raw) > 80 else "")})
            continue
        text = plain(raw)
        if not text:
            dropped.append({"id": it.get("id"), "reason": "empty after markup removal",
                            "clause": raw[:80]})
            continue
        row = {"id": it.get("id"), "text": text}
        if keep_source:
            row["source_clause"] = raw
        kept.append(row)
    return kept, dropped


def main():
    ap = argparse.ArgumentParser(description="NL control set from a clause dataset")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", default="NL-control-set.json")
    ap.add_argument("--key", default="clause", help="field holding the clause text")
    ap.add_argument("--keep-source", action="store_true",
                    help="also carry the original clause, for auditing")
    ap.add_argument("--report", default=None, help="write the drop log here")
    args = ap.parse_args()

    items = json.load(open(args.input, encoding="utf-8"))
    kept, dropped = build(items, args.key, args.keep_source)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(kept, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"{len(items)} in → {len(kept)} NL rules, {len(dropped)} dropped → {args.out}",
          file=sys.stderr)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(dropped, fh, indent=2, ensure_ascii=False)
        print(f"drop log → {args.report}", file=sys.stderr)
    else:
        for d in dropped:
            print(f"   drop #{d['id']:<4} {d['reason']:<28} {d['clause'][:52]}", file=sys.stderr)


if __name__ == "__main__":
    main()
