"""Token → USD accounting with a hard cap.

The cap is read from `JUDGE_MAX_USD` at boot. Running spend persists in the
`crawl_settings` table under key `judge_spend_usd` so a container restart
doesn't reset the meter mid-batch. Reset manually by deleting the row.

Pricing is for Haiku 4.5 routed through Perplexity (pass-through, no markup
per the prototype's comment). If we ever flip the model, update these
constants in lockstep — there's no per-model pricing table yet.
"""

import os
from typing import Optional

import duckdb


INPUT_USD_PER_MTOK = float(os.environ.get("JUDGE_INPUT_USD_PER_MTOK", "1.00"))
OUTPUT_USD_PER_MTOK = float(os.environ.get("JUDGE_OUTPUT_USD_PER_MTOK", "5.00"))

# Fallback estimates used when the upstream API doesn't return usage counts.
# Conservative: better to over-count and stop early than to undercount and
# blow through the cap.
EST_INPUT_TOKENS = 3000
EST_OUTPUT_TOKENS = 300


class BudgetExceeded(Exception):
    pass


class Budget:
    def __init__(self, con: duckdb.DuckDBPyConnection, max_usd: Optional[float] = None) -> None:
        self.con = con
        # Cap precedence: explicit arg > persisted crawl_settings.judge_max_usd > env var > $1.00.
        # The persisted value lets the UI bump the cap at runtime and have it
        # survive container restarts.
        if max_usd is None:
            persisted = self._load_persisted_cap()
            max_usd = (
                persisted
                if persisted is not None
                else float(os.environ.get("JUDGE_MAX_USD", "1.00"))
            )
        self.max_usd = float(max_usd)
        self.spent_usd = self._load_spent()

    def _load_persisted_cap(self) -> Optional[float]:
        row = self.con.execute(
            "SELECT value FROM crawl_settings WHERE key = 'judge_max_usd'"
        ).fetchone()
        return float(row[0]) if row else None

    def _load_spent(self) -> float:
        row = self.con.execute(
            "SELECT value FROM crawl_settings WHERE key = 'judge_spend_usd'"
        ).fetchone()
        return float(row[0]) if row else 0.0

    def set_cap(self, new_max_usd: float) -> None:
        self.max_usd = float(new_max_usd)
        self.con.execute(
            """
            INSERT INTO crawl_settings (key, value) VALUES ('judge_max_usd', ?)
            ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = now()
            """,
            [f"{self.max_usd:.6f}"],
        )

    def reset_spend(self) -> None:
        self.spent_usd = 0.0
        self.con.execute("DELETE FROM crawl_settings WHERE key = 'judge_spend_usd'")

    @staticmethod
    def cost(input_tokens: int, output_tokens: int) -> float:
        return (
            (input_tokens / 1_000_000) * INPUT_USD_PER_MTOK
            + (output_tokens / 1_000_000) * OUTPUT_USD_PER_MTOK
        )

    def would_exceed(
        self,
        est_input: int = EST_INPUT_TOKENS,
        est_output: int = EST_OUTPUT_TOKENS,
    ) -> bool:
        return self.spent_usd + self.cost(est_input, est_output) > self.max_usd

    def add(self, input_tokens: int, output_tokens: int) -> None:
        delta = self.cost(input_tokens, output_tokens)
        self.spent_usd += delta
        self.con.execute(
            """
            INSERT INTO crawl_settings (key, value) VALUES ('judge_spend_usd', ?)
            ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = now()
            """,
            [f"{self.spent_usd:.6f}"],
        )
        if self.spent_usd > self.max_usd:
            raise BudgetExceeded(
                f"spent ${self.spent_usd:.4f} > cap ${self.max_usd:.4f}"
            )
