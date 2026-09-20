"""MotherDuck as an input source: read rule files straight from the cloud warehouse.

The crawler that populates MotherDuck uses different column names than the Hugging Face
corpus does, so this module's only real job is the mapping — it pulls the `files` table
and renames its columns to the canonical set the parser expects:

    canonical         MotherDuck `files`     notes
    ────────────────────────────────────────────────────────────────────────────────
    repo           ←  repo_name              owner/repo | dataset id | domain
    path           ←  file_path              path within the repo
    link           ←  source_url             human-facing URL
    content_sha256 ←  content_hash           sha256(content) — versions the clause ids
    file           ←  content                the document text itself
    stars          ←  (absent)               defaults to 0; the crawler doesn't record it

Every mapping is overridable from the environment (see config.MD_COLUMNS), so a table
with a different shape needs no code change.

Reads only. Nothing here writes to MotherDuck — the clauses still go to Hugging Face.
"""
import pyarrow as pa

from .config import (MD_COLUMNS, MOTHERDUCK_DB, MOTHERDUCK_TOKEN, MD_FILES_TABLE,
                     FILES_TEXT_COLUMN)

# Canonical columns the extractor needs. `stars` is optional and defaults to 0.
REQUIRED = ("repo", "path", "content_sha256")


def _duckdb():
    try:
        import duckdb
    except ImportError:
        raise RuntimeError("duckdb is not installed — `pip install duckdb`")
    return duckdb


def connect(token=None, db=None):
    """Open a MotherDuck session. The token is never logged or echoed."""
    token = token or MOTHERDUCK_TOKEN
    db = db or MOTHERDUCK_DB
    if not token:
        raise RuntimeError(
            "MOTHERDUCK_TOKEN is not set. Put it in .env (MOTHERDUCK_TOKEN=...) or export "
            "it, then re-run. Get one from https://app.motherduck.com → Settings → Access Tokens.")
    # `md:<db>?motherduck_token=...` connects straight to the database, so a hyphenated
    # name like `daily-extraction` never needs quoting in a USE statement.
    return _duckdb().connect(f"md:{db}?motherduck_token={token}")


def _select(columns, table, where=None, limit=0):
    """Build the projection that renames source columns to the canonical names."""
    parts = []
    for canon, src in columns.items():
        if src:
            parts.append(f'"{src}" AS "{canon}"')
        elif canon == "stars":
            parts.append('0 AS "stars"')
        else:
            parts.append(f'NULL AS "{canon}"')
    sql = f'SELECT {", ".join(parts)} FROM "{table}"'
    if where:
        sql += f" WHERE {where}"
    sql += f' ORDER BY "{columns.get("repo") or 1}", "{columns.get("path") or 1}"'
    if limit:
        sql += f" LIMIT {int(limit)}"
    return sql


def read_files(token=None, db=None, table=None, where=None, limit=0, columns=None,
               con=None):
    """The rule-file corpus from MotherDuck as a pyarrow Table with canonical columns.

    `where` is raw SQL appended to the query — use it to scope a run, e.g.
    `--where "file_type = 'CLAUDE.md' AND content_len < 100000"`. It is your SQL, run
    against your warehouse; nothing here sanitizes it."""
    cols = dict(columns or MD_COLUMNS)
    cols.setdefault(FILES_TEXT_COLUMN, cols.pop("text", None) or "content")
    own = con is None
    con = con or connect(token, db)
    try:
        sql = _select(cols, table or MD_FILES_TABLE, where, limit)
        res = con.execute(sql)
        # duckdb >=1.3 returns a RecordBatchReader from .arrow(); fetch_arrow_table()
        # gives a materialized Table on every version we support.
        tbl = (res.fetch_arrow_table() if hasattr(res, "fetch_arrow_table")
               else pa.Table.from_batches(res.arrow()))
    finally:
        if own:
            con.close()

    missing = [c for c in REQUIRED if c not in tbl.column_names]
    if missing:
        raise RuntimeError(f"MotherDuck query produced no {missing} column(s) — "
                           f"check MD_COLUMNS mapping. Got: {', '.join(tbl.column_names)}")
    if FILES_TEXT_COLUMN not in tbl.column_names:
        raise RuntimeError(f"no '{FILES_TEXT_COLUMN}' text column in the result — "
                           "set HF_FILES_TEXT_COLUMN or MD_TEXT_COLUMN.")
    # stars is advisory; make sure it is present and typed so the schema cast is clean.
    if "stars" not in tbl.column_names:
        tbl = tbl.append_column("stars", pa.array([0] * tbl.num_rows, type=pa.int64()))
    return tbl


def probe(token=None, db=None, table=None):
    """Connectivity + schema check. Returns a dict; raises with a clear message on
    failure. Run this first — `python -m clause_extraction.run --md-probe`."""
    con = connect(token, db)
    try:
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        t = table or MD_FILES_TABLE
        out = {"database": db or MOTHERDUCK_DB, "tables": tables, "files_table": t,
               "present": t in tables}
        if out["present"]:
            out["columns"] = [r[0] for r in con.execute(f'DESCRIBE "{t}"').fetchall()]
            out["rows"] = con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
            out["unmapped"] = [f"{c} -> {s}" for c, s in MD_COLUMNS.items()
                               if s and s not in out["columns"]]
        return out
    finally:
        con.close()


__all__ = ["connect", "read_files", "probe", "REQUIRED"]
