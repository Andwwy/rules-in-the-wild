"""The vote's deterministic routing and the rails on the judge's answer."""
from rule_pipeline import vote


def attempt(enforcer=(), target=(), trigger=(), spec=""):
    return {"clause_id": "c1", "rule_text": "r", "context": "c", "enforcer": list(enforcer), "target": list(target),
            "trigger": list(trigger), "spec": spec}


def test_fewer_than_two_named_is_null_without_the_model():
    values, how, ask = vote.plan([attempt(enforcer=["ESLint"]), attempt(), attempt()])
    assert values["enforcer"] == [] and how["enforcer"] == "null" and ask == []


def test_same_value_up_to_spelling_is_taken_without_the_model():
    values, how, ask = vote.plan([attempt(enforcer=["`ESLint`"]), attempt(enforcer=["eslint"]), attempt(enforcer=["ESLint"])])
    assert how["enforcer"] == "pattern" and len(values["enforcer"]) == 1 and ask == []


def test_disagreement_goes_to_the_model():
    assert vote.plan([attempt(enforcer=["ESLint"]), attempt(enforcer=["Prettier"]), attempt(enforcer=["ESLint"])])[2] == ["enforcer"]


def test_rails_keep_cited_literal_values_and_drop_the_rest():
    attempts = [attempt(enforcer=["ESLint"]), attempt(enforcer=["ESLint with plugin"]), attempt(enforcer=["ESLint"])]
    order = [0, 1, 2]
    answer = [{"value": "ESLint", "attempts": [1, 3]},            # cited twice, literal           → kept
              {"value": "ESLint with plugin", "attempts": [2]},   # only one citation              → dropped
              {"value": "A linter", "attempts": [1, 2, 3]}]       # not a string any attempt gave  → dropped
    values, kept, dropped = vote.apply_rails(attempts, order, "enforcer", answer)
    assert values == ["ESLint"] and [d["value"] for d in dropped] == ["ESLint with plugin", "A linter"]


def test_no_surviving_value_is_no_consensus_and_spec_comes_from_a_replicate():
    attempts = [attempt(enforcer=["A"], spec="spec A"), attempt(enforcer=["B"], spec="spec B"), attempt(enforcer=["C"], spec="spec C")]
    record = vote.resolve(attempts, answer={"enforcer": [], "target": [], "trigger": []}, usage={})
    assert record["enforcer"] == [] and record["vote"]["how"]["enforcer"] == "no_consensus" and record["spec"] == ""
    agreed = vote.resolve([attempt(enforcer=["A"], spec="first"), attempt(enforcer=["A"], spec="second"), attempt()])
    assert agreed["enforcer"] == ["A"] and agreed["spec"] == "first" and agreed["vote"]["stability"] == "2/3"
