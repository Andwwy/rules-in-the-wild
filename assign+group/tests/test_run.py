"""The whole pipeline through the command line, with a fake model: the wiring, the run folder, and resume."""
import json
from pathlib import Path
from unittest.mock import patch

from rule_pipeline import llm, run

ROOT = Path(__file__).resolve().parent.parent
calls = []


def fake_model(prompt, user_input, schema, settings):
    calls.append(settings.effort)
    wanted = schema["properties"]
    if "classes" in wanted:                                    # stage 3b: everything into one class
        ids = [int(line.split(".")[0]) for line in user_input.splitlines()]
        return {"classes": [{"class": "Where it runs", "members": ids}]}, {"cost": 0.01}
    if "spec" in wanted:                                       # stage 1: name an enforcer for rules that mention a tool
        named = "lint" in user_input.lower() or "test" in user_input.lower()
        return {"enforcer": ["ESLint"] if named else [], "target": ["source files"], "trigger": ["on commit"],
                "spec": "check it"}, {"cost": 0.002}
    return {"enforcer": [], "target": [], "trigger": []}, {"cost": 0.001}      # stage 2: the judge


def test_end_to_end_then_resume_then_the_optional_class_stage(tmp_path):
    argv = [str(ROOT / "examples" / "rules.sample.json"), "--out", str(tmp_path), "--workers", "4"]
    with patch.object(llm, "call", fake_model):
        run.main(argv)
        first = len(calls)
        run.main(argv)
        assert len(calls) == first, "the second run must not call the model"

        rules = json.loads((tmp_path / "rules.json").read_text())
        result = json.loads((tmp_path / "result.json").read_text())
        summary = json.loads((tmp_path / "run.json").read_text())
        assert first == 3 * len(rules), "3 replicates per rule; the fake always agrees, so no judge call; grouping needs no model"
        assert [r["clause_id"] for r in result] == [r["clause_id"] for r in rules]
        assert not (tmp_path / "classes.json").exists()
        for record in result:
            assert [c["enforcer"] for c in record["categories"]] == record["enforcer"]
            assert all(c["subcategory"] == "ESLint" and c["class"] is None for c in record["categories"])
        assert summary["prompts"]["assignment"]["version"] == "v1.19" and summary["stages"] == ["assign", "vote", "subcategory"]
        assert summary["settings"]["assign"]["workers"] == 4 and summary["settings"]["assign"]["batch_size"] == 1
        assert summary["settings"]["vote"]["effort"] == "medium" and summary["unfinished"] == {f"assign.rep{n}.jsonl": 0 for n in (1, 2, 3)}

        run.main(argv + ["--stages", "class"])                   # a separate stage on the same run folder
        assert len(calls) == first + 1, "exactly one more request"
        result = json.loads((tmp_path / "result.json").read_text())
        assert all(c["class"] == "Where it runs" for record in result for c in record["categories"])
        run.main(argv)                                           # the default stages again: the classes are kept
        assert len(calls) == first + 1
        assert all(c["class"] == "Where it runs" for r in json.loads((tmp_path / "result.json").read_text()) for c in r["categories"])
