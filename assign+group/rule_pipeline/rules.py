"""Load the rules to process — from a JSON file in our schema, or straight from the online DB — and check them.

A rule is a dict. Required: clause_id, rule_text, context. The other keys of our draw schema are carried through untouched.
`context` must be in the current format: heading path, blank line, then the window around the clause (code elided as ⋯).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

REQUIRED = ("clause_id", "rule_text", "context")
CARRIED = ("text_sha", "heading_path", "repo", "path", "link", "stars", "n_dup_text", "is_rule", "is_rule_source")


def load_json(path: str | Path) -> list[dict]:
    rules = json.loads(Path(path).read_text())
    if not isinstance(rules, list):
        raise ValueError(f"{path}: expected a JSON list of rule objects")
    return validate(rules)


def load_db(db: str = "rules", table: str = "rule_draw", where: str | None = None, limit: int | None = None) -> list[dict]:
    """Read rules from MotherDuck (read-only). Needs MOTHERDUCK_TOKEN and `pip install duckdb`.

    `where` is your own SQL, run against your own warehouse, e.g. "draw = 'rule 10000 (judge v1)' AND stars > 100".
    """
    try:
        import duckdb
    except ImportError:
        raise SystemExit("reading from the DB needs duckdb:  pip install 'rule-pipeline[db]'")
    token = os.environ.get("MOTHERDUCK_TOKEN")
    if not token:
        raise SystemExit("MOTHERDUCK_TOKEN is not set — put it in .env or export it")
    if not re.fullmatch(r"[A-Za-z_][\w.]*", table):
        raise ValueError(f"not a table name: {table!r}")

    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY clause_id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    con = duckdb.connect(f"md:{db}", config={"motherduck_token": token})
    try:
        cursor = con.execute(sql)
        columns = [c[0] for c in cursor.description]
        rules = [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        con.close()
    return validate(rules)


def validate(rules: list[dict]) -> list[dict]:
    """Fail loudly, naming the offending rules. Returns the rules trimmed to the known keys."""
    problems = []
    seen = set()
    for n, rule in enumerate(rules):
        name = rule.get("clause_id") or f"#{n}"
        missing = [k for k in REQUIRED if not isinstance(rule.get(k), str) or not rule[k].strip()]
        if missing:
            problems.append(f"{name}: missing or empty {missing}")
        if rule.get("clause_id") in seen:
            problems.append(f"{name}: duplicate clause_id")
        seen.add(rule.get("clause_id"))
        if rule.get("is_rule") is False:
            problems.append(f"{name}: is_rule is false — only rules go through assignment")
    if problems:
        shown = "\n  ".join(problems[:10])
        raise ValueError(f"{len(problems)} problem(s) in the input rules:\n  {shown}" + ("\n  …" if len(problems) > 10 else ""))
    if not rules:
        raise ValueError("no rules to process")
    return [{k: rule[k] for k in (*REQUIRED, *CARRIED) if k in rule} for rule in rules]
