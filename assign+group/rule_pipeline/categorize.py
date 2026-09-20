"""Stage 3 — grouping the voted enforcers. Two levels, two separate steps:

    subcategory   DETERMINISTIC, no model. Each voted enforcer value is matched against aliases.json (regex → name, first
                  match wins); a value that matches nothing is its own subcategory, verbatim. This is where the pipeline ends
                  by default.
    class         OPTIONAL, one model call (`--stages class`). Groups all subcategories by where the enforcement runs. The
                  answer must be an exact partition of the subcategory ids; ids it missed or repeated are placed by a small
                  follow-up call.

Only rules with a voted enforcer AND target AND trigger are categorised (a full triple), as in the lab runs.
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path

from . import llm

CLASSES_SCHEMA = {"type": "object", "required": ["classes"], "properties": {"classes": {"type": "array", "items": {
    "type": "object", "required": ["class", "members"],
    "properties": {"class": {"type": "string"}, "members": {"type": "array", "items": {"type": "integer"}}}}}}}
PLACEMENTS_SCHEMA = {"type": "object", "required": ["placements"], "properties": {"placements": {"type": "array", "items": {
    "type": "object", "required": ["id", "class"],
    "properties": {"id": {"type": "integer"}, "class": {"type": "string"}}}}}}


# ── subcategory ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def load_aliases(path: Path) -> list[tuple[re.Pattern, str]]:
    return [(re.compile(pattern, re.I), name) for pattern, name in json.loads(Path(path).read_text())]


def alias(value: str, aliases: list[tuple[re.Pattern, str]]) -> str:
    value = value.strip()
    return next((name for pattern, name in aliases if pattern.search(value)), value)


def subcategories(voted: list[dict], aliases, full_triples_only: bool = True) -> tuple[list[dict], list[dict]]:
    """→ (subcategories, rows).

    subcategories: [{id, name, rules, variants}] — biggest first; `variants` are its most common raw values.
    rows:          [{clause_id, enforcer, subcategory}] — one per enforcer value of a categorised rule.
    """
    rules_of, variants_of, rows = collections.defaultdict(set), collections.defaultdict(collections.Counter), []
    for record in voted:
        if not record["enforcer"] or (full_triples_only and not (record["target"] and record["trigger"])):
            continue
        for value in dict.fromkeys(record["enforcer"]):
            name = alias(value, aliases)
            rules_of[name].add(record["clause_id"])
            variants_of[name][value.strip()] += 1
            rows.append({"clause_id": record["clause_id"], "enforcer": value, "subcategory": name})
    ranked = sorted(rules_of, key=lambda name: (-len(rules_of[name]), name.lower()))
    subcats = [{"id": n, "name": name, "rules": len(rules_of[name]),
                "variants": [v for v, _ in variants_of[name].most_common(4)]} for n, name in enumerate(ranked, 1)]
    return subcats, rows


# ── class ────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def describe(subcat: dict) -> str:
    """One line of the listing the model sees: `id. name (n rules) — other raw values`."""
    others = [v for v in subcat["variants"] if v != subcat["name"]]
    line = f'{subcat["id"]}. {subcat["name"]} ({subcat["rules"]} rules)'
    return line + (" — " + "; ".join(others) if others else "")


def problems(classes: list[dict], ids: set[int]) -> dict:
    placed = [m for c in classes for m in c["members"]]
    counts = collections.Counter(placed)
    return {"missed": sorted(ids - set(placed)),
            "repeated": sorted(m for m, n in counts.items() if n > 1),
            "invented": sorted(set(placed) - ids),
            "empty": [c["class"] for c in classes if not c["members"]]}


def repair_request(classes: list[dict], todo: list[int], by_id: dict) -> str:
    current = "\n".join(f'- "{c["class"]}": ' + ", ".join(f'{m} {by_id[m]["name"]}' for m in c["members"]) for c in classes)
    items = "\n".join(describe(by_id[i]) for i in todo)
    return (f"CURRENT GROUPING (class name: member ids with names):\n{current}\n\n"
            "The following category ids were missed or placed in more than one class in the grouping above. "
            "Place each of them into exactly ONE class: reuse an existing class name verbatim when the category fits it, "
            f"otherwise give a new class name. Do not touch any other id.\n{items}")


def place(classes: list[dict], placements: list[dict], todo: list[int]) -> list[dict]:
    """Move each repaired id into the class the model named for it (a new class if the name is new)."""
    by_name = {c["class"]: c for c in classes}
    for p in placements:
        if p["id"] not in todo:
            continue
        for c in classes:
            c["members"] = [m for m in c["members"] if m != p["id"]]
        if p["class"] not in by_name:
            by_name[p["class"]] = {"class": p["class"], "members": []}
            classes.append(by_name[p["class"]])
        by_name[p["class"]]["members"].append(p["id"])
    return [c for c in classes if c["members"]]


def group(subcats: list[dict], prompt: str, settings: llm.Settings, max_repairs: int = 4) -> tuple[list[dict], list[dict]]:
    """One call over all subcategories → (classes, repair history). Raises if the partition cannot be made exact."""
    by_id = {s["id"]: s for s in subcats}
    ids = set(by_id)
    answer, _ = llm.call(prompt, "\n".join(describe(s) for s in subcats), CLASSES_SCHEMA, settings)
    classes = [{"class": c["class"], "members": [m for m in c["members"] if m in ids]} for c in answer["classes"]]
    classes = [c for c in classes if c["members"]]

    history = []
    for round_number in range(1, max_repairs + 1):
        found = problems(classes, ids)
        todo = sorted(set(found["missed"]) | set(found["repeated"]))
        if not todo:
            break
        print(f"  classes: repair round {round_number} for ids {todo}", flush=True)
        reply, _ = llm.call(prompt, repair_request(classes, todo, by_id), PLACEMENTS_SCHEMA, settings)
        history.append({"round": round_number, "todo": todo, "placements": reply["placements"]})
        classes = place(classes, reply["placements"], todo)

    left = {k: v for k, v in problems(classes, ids).items() if v}
    if left:
        raise RuntimeError(f"the class grouping is still not an exact partition after {max_repairs} repairs: {left}")
    return classes, history


def classify(subcats: list[dict], prompt: str, settings: llm.Settings, out_dir: Path, class_names: dict | None = None) -> dict:
    """The optional model step → {subcategory: class}. Writes classes.json; reuses it if it still covers the same subcategories.

    `class_names` optionally maps the model's class name to a shorter display name; the model's name is kept as class_long.
    """
    saved = load_classes(out_dir, subcats)
    if saved is not None:
        print("class: reused classes.json", flush=True)
        return saved
    grouped, history = group(subcats, prompt, settings)
    by_id = {s["id"]: s["name"] for s in subcats}
    found = [{"class": (class_names or {}).get(c["class"], c["class"]), "class_long": c["class"],
              "subcategories": [by_id[m] for m in c["members"]]} for c in grouped]
    (out_dir / "classes.json").write_text(json.dumps({"classes": found, "repairs": history}, ensure_ascii=False, indent=1) + "\n")
    print(f"class: {len(found)} classes", flush=True)
    return {name: c["class"] for c in found for name in c["subcategories"]}


def load_classes(out_dir: Path, subcats: list[dict]) -> dict | None:
    """{subcategory: class} from an earlier class step, if it covers exactly these subcategories."""
    saved = out_dir / "classes.json"
    if not saved.exists():
        return None
    found = json.loads(saved.read_text())["classes"]
    class_of = {name: c["class"] for c in found for name in c["subcategories"]}
    return class_of if sorted(class_of) == sorted(s["name"] for s in subcats) else None
