"""MotherDuck connection helper. Parallels prototype/src/db.py at a smaller
scope: this agent is read/write-light and never bootstraps the schema — the
prototype's crawler already ran `db/duckdb_schema.sql` on first connect.

If you want to point at a local file for dev, unset `MOTHERDUCK_TOKEN` and set
`DUCKDB_PATH=/data/rules.duckdb`. The connect string switches automatically.
"""

import os

import duckdb


USING_MOTHERDUCK = bool(os.environ.get("MOTHERDUCK_TOKEN"))
MOTHERDUCK_DB = os.environ.get("MOTHERDUCK_DB", "rules_in_the_wild")
DUCKDB_PATH = os.environ.get("DUCKDB_PATH", "/data/rules.duckdb")


def connect() -> duckdb.DuckDBPyConnection:
    target = f"md:{MOTHERDUCK_DB}" if USING_MOTHERDUCK else DUCKDB_PATH
    return duckdb.connect(target)


def enum_values(c: duckdb.DuckDBPyConnection, type_name: str) -> list[str]:
    row = c.execute(f"SELECT enum_range(NULL::{type_name})").fetchone()
    if not row or not row[0]:
        return []
    return list(row[0])
