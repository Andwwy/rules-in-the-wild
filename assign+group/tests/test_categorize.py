"""Aliases, the partition check and the repair loop — with a fake model."""
import json
from unittest.mock import patch

import pytest

from rule_pipeline import categorize, llm

ALIASES = [("^eslint.*", "ESLint"), ("lint", "Some linter")]


def voted(clause_id, enforcer, full=True):
    return {"clause_id": clause_id, "enforcer": enforcer, "target": ["t"] if full else [], "trigger": ["when"] if full else []}


def aliases(tmp_path):
    (tmp_path / "aliases.json").write_text(json.dumps(ALIASES))
    return categorize.load_aliases(tmp_path / "aliases.json")


def test_first_alias_wins_and_unmatched_values_stay_verbatim(tmp_path):
    a = aliases(tmp_path)
    assert categorize.alias("ESLint with a plugin", a) == "ESLint"          # also matches "lint", but the first rule wins
    assert categorize.alias("stylelint", a) == "Some linter"
    assert categorize.alias(" PostgreSQL ", a) == "PostgreSQL"


def test_only_full_triples_are_categorised_unless_asked(tmp_path):
    records = [voted("c1", ["ESLint"]), voted("c2", ["eslint v9"]), voted("c3", ["PostgreSQL"], full=False)]
    subcats, rows = categorize.subcategories(records, aliases(tmp_path))
    assert [(s["id"], s["name"], s["rules"]) for s in subcats] == [(1, "ESLint", 2)]
    assert len(categorize.subcategories(records, aliases(tmp_path), full_triples_only=False)[0]) == 2


SUBCATS = [{"id": n, "name": name, "rules": 1, "variants": [name]} for n, name in enumerate(["ESLint", "Jest", "PostgreSQL", "pre-commit"], 1)]


def test_missed_and_repeated_ids_are_repaired_into_an_exact_partition():
    replies = iter([
        {"classes": [{"class": "Static", "members": [1, 2]}, {"class": "Test", "members": [2, 99]}]},   # 2 twice, 3 and 4 missed, 99 invented
        {"placements": [{"id": 2, "class": "Test"}, {"id": 3, "class": "Database"}, {"id": 4, "class": "Static"}]},
    ])
    with patch.object(llm, "call", lambda *a, **k: (next(replies), {})):
        classes, history = categorize.group(SUBCATS, "prompt", llm.Settings())
    assert {c["class"]: sorted(c["members"]) for c in classes} == {"Static": [1, 4], "Test": [2], "Database": [3]}
    assert len(history) == 1 and history[0]["todo"] == [2, 3, 4]


def test_gives_up_loudly_when_the_partition_cannot_be_fixed():
    with patch.object(llm, "call", lambda *a, **k: ({"classes": [{"class": "A", "members": [1]}], "placements": []}, {})):
        with pytest.raises(RuntimeError, match="not an exact partition"):
            categorize.group(SUBCATS, "prompt", llm.Settings(), max_repairs=2)
