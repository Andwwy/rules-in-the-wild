"""run_many: threading, resume, and batching — with a fake model, no network."""
import json
from unittest.mock import patch

from rule_pipeline import llm

SCHEMA = {"type": "object", "properties": {"echo": {"type": "string"}}, "required": ["echo"]}
ITEMS = [{"clause_id": f"c{n}", "text": f"rule {n}"} for n in range(7)]


def record(item, answer, usage, error):
    return {"clause_id": item["clause_id"], "echo": (answer or {}).get("echo"), **({"error": error} if error else {})}


def run(tmp_path, fake, **settings):
    with patch.object(llm, "call", fake):
        return llm.run_many(ITEMS, key="clause_id", make_input=lambda i: i["text"], to_record=record, prompt="p",
                            schema=SCHEMA, settings=llm.Settings(**settings), checkpoint=tmp_path / "ck.jsonl")


def test_every_item_once_and_resume_calls_nothing(tmp_path):
    calls = []
    def fake(prompt, user_input, schema, settings):
        calls.append(user_input)
        return {"echo": user_input}, {"cost": 0.001}
    done = run(tmp_path, fake, workers=3)
    assert {k: v["echo"] for k, v in done.items()} == {i["clause_id"]: i["text"] for i in ITEMS}
    assert len(calls) == 7
    run(tmp_path, fake, workers=3)
    assert len(calls) == 7, "a second run must not call the model again"


def test_failed_items_are_retried_on_the_next_run(tmp_path):
    def flaky(prompt, user_input, schema, settings):
        if user_input == "rule 3":
            raise llm.LLMError("boom")
        return {"echo": user_input}, {}
    assert run(tmp_path, flaky)["c3"]["error"] == "boom"
    fixed = run(tmp_path, lambda p, u, s, st: ({"echo": u}, {}))
    assert fixed["c3"]["echo"] == "rule 3" and "error" not in fixed["c3"]


def test_batch_reply_that_drops_or_invents_a_key_is_redone_one_by_one(tmp_path):
    sizes = []
    def fake(prompt, user_input, schema, settings):
        if "results" not in schema["properties"]:                  # a single-item request
            sizes.append(1)
            return {"echo": user_input}, {}
        blocks = [b for b in user_input.split("### clause_id = ")[1:]]
        sizes.append(len(blocks))
        results = [{"clause_id": b.split("\n")[0], "echo": b.split("\n")[1]} for b in blocks]
        results = [r for r in results if r["clause_id"] != "c1"] + [{"clause_id": "ghost", "echo": "?"}]
        return {"results": results}, {"cost": 0.003}
    done = run(tmp_path, fake, batch_size=3, workers=2)
    assert sorted(done) == sorted(i["clause_id"] for i in ITEMS), "every rule exactly once, the invented key ignored"
    assert done["c1"]["echo"] == "rule 1"
    assert sorted(sizes) == [1, 1, 3, 3], "batches of 3, 3 and 1, plus c1 redone alone"
    lines = [json.loads(l) for l in (tmp_path / "ck.jsonl").read_text().splitlines()]
    assert len(lines) == 7


def test_a_rejected_key_stops_the_run_instead_of_failing_every_item(tmp_path):
    calls = []
    def refused(prompt, user_input, schema, settings):
        calls.append(user_input)
        raise llm.FatalLLMError("perplexity refused the request (401): insufficient_quota")
    import pytest
    with pytest.raises(SystemExit, match="insufficient_quota"):
        run(tmp_path, refused, workers=1)
    assert len(calls) == 1 and not (tmp_path / "ck.jsonl").read_text(), "one request, nothing recorded as a failed item"
