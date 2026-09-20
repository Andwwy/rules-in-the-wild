"""The rewrite must reproduce the lab's recorded v1.11 run exactly. Needs the local data/ folder; skipped without it."""
import json
from pathlib import Path

import pytest

from rule_pipeline import categorize, vote

ROOT = Path(__file__).resolve().parent.parent
PASS = ROOT / "data" / "pass1.11-10000"
pytestmark = pytest.mark.skipif(not PASS.exists(), reason="the recorded v1.11 run is not in data/ (it is not part of the repo)")


def load(path):
    return json.loads(Path(path).read_text())


@pytest.fixture(scope="module")
def recorded():
    return load(PASS / "v1.11_result" / "assignment output.json")


def test_vote_reproduces_the_recorded_vote(recorded):
    replicates = [{r["clause_id"]: r for r in load(PASS / f"v1.11.{n}" / "assignment output.json")} for n in (1, 2, 3)]
    different = []
    for old in recorded:
        if old.get("error"):
            continue
        attempts = [rep[old["clause_id"]] for rep in replicates]
        new = vote.resolve(attempts, answer=old["vote"].get("model_output"), usage=old.get("usage"))
        # value ORDER is not compared: the lab script iterated a set, so its order changed from process to process
        same = (all(sorted(new[k]) == sorted(old[k]) for k in ("enforcer", "target", "trigger")) and new["spec"] == old["spec"]
                and new["vote"]["how"] == old["vote"]["how"]
                and new["vote"]["stability"] == old["vote"]["stability"]
                and [name[-1] for name in new["vote"]["attempt_order"]] == [name[-1] for name in old["vote"]["attempt_order"]])
        if not same:
            different.append(old["clause_id"])
    assert not different, f"{len(different)} of {len(recorded)} rules vote differently, e.g. {different[:5]}"


def test_subcategories_reproduce_the_recorded_categories(recorded):
    subcats, rows = categorize.subcategories(recorded, categorize.load_aliases(ROOT / "aliases.json"))
    old = {c["name"]: c["rules"] for c in load(PASS / "one call grouping" / "categories.json")}
    assert {s["name"]: s["rules"] for s in subcats} == old
    assert len({r["clause_id"] for r in rows}) == 1841 and len(rows) == 1875
