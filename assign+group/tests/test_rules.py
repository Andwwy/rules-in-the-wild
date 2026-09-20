import pytest

from rule_pipeline.rules import validate

GOOD = {"clause_id": "a", "rule_text": "Use X.", "context": "H\n\n- Use X.", "repo": "o/r", "extra": "dropped"}


def test_keeps_known_keys_only():
    assert validate([GOOD]) == [{"clause_id": "a", "rule_text": "Use X.", "context": "H\n\n- Use X.", "repo": "o/r"}]


@pytest.mark.parametrize("bad, message", [
    ([{**GOOD, "context": ""}], "missing or empty"),
    ([GOOD, GOOD], "duplicate clause_id"),
    ([{**GOOD, "is_rule": False}], "is_rule is false"),
    ([], "no rules"),
])
def test_problems_are_named(bad, message):
    with pytest.raises(ValueError, match=message):
        validate(bad)
