"""Every test writes to its own spend ledger, never the project's (rules in the wild/spend.jsonl)."""
import pytest


@pytest.fixture(autouse=True)
def private_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("RITW_SPEND_LEDGER", str(tmp_path / "spend.jsonl"))
    monkeypatch.setenv("RITW_BUDGET_USD", "50")
    return tmp_path / "spend.jsonl"
