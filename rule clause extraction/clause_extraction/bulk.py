"""Bulk extraction: the whole MotherDuck corpus → rule_clause, non-structural only.

Three stages, each independently resumable, driven one hex slice at a time:

    download   16 sliced GROUP BY queries (one per leading hex digit of content_sha256)
               → local/files-<d>.parquet.  Sliced because the un-sliced aggregate needs
               7.4 GiB of server memory against a 1.8 GiB instance and OOMs.
    parse      local parquet → 8 worker processes → staging/clauses-<d>-<n>.parquet.
               Structural units (heading / code / table_header) are dropped here, so
               they never reach the warehouse.
    load       INSERT INTO rule_clause SELECT * FROM read_parquet(staged) — one
               statement per staged file, therefore one transaction, therefore atomic.
               Staged files are deleted only after their insert commits.

Idempotency comes from the download query's anti-join against rule_clause, NOT from a
primary key: a unique index over ~54M rows costs ~3.5 GB, which does not fit the
instance. Batches are file-aligned, so a committed batch never holds a partial file.

    python -m clause_extraction.bulk --create-table
    python -m clause_extraction.bulk --slice 0          # download+parse+load one slice
    python -m clause_extraction.bulk --all              # all 16
"""
import argparse
import glob
import hashlib
import multiprocessing as mp
import os
import re
import time

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from .config import BASE_DIR, MOTHERDUCK_DB, MOTHERDUCK_TOKEN
from .grammar import (STRUCTURAL_TYPES, _line_offsets, heading_path_at,
                      heading_spans, line_of, segment)

LOCAL = os.path.join(BASE_DIR, "local")
STAGING = os.path.join(BASE_DIR, "staging")
SLICES = "0123456789abcdef"
FILES_PER_BATCH = 2000          # keeps a worker's rows well under a GB
WORKERS = 8                     # measured plateau; 10 buys nothing
_WS = re.compile(r"\s+")

# `*_assign` hold open-assignment sem_mapping results and sit beside the slot they map.
# Like the other label columns they are written NULL by extraction — a later pass fills them.
# Context rides on the row since the v2.2 re-cut — no second table, no id join.
# The window is ASYMMETRIC on purpose: the scoping signal (section heading, the
# lead-in that governs a list) sits ABOVE the clause — measured median 5 lines up,
# p90 34 — while the lines below only serve to show sibling shape ("is this one
# entry in a homogeneous list?"), which 2 lines settle. A symmetric ±5 window spent
# half its budget on the next section bleeding in.
CTX_BEFORE, CTX_AFTER = 8, 2

_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _fenced(lines):
    """Per-line mask: True inside a fenced code block (markers included).

    Code lines are skipped when filling the context window — a dangling snippet
    from the previous example crowds out the prose that actually scopes the
    clause (the lead-in, the sibling bullets). Measured: without this, over half
    the before-window on long sections is spent on fence tails."""
    mask, fence = [False] * len(lines), None
    for i, ln in enumerate(lines):
        m = _FENCE_RE.match(ln)
        if m:
            mask[i] = True
            fence = None if (fence and ln.strip().startswith(fence)) else (fence or m.group(1))
        elif fence is not None:
            mask[i] = True
    return mask


def _context(lines, mask, cl0, cl1):
    """The rendered context block for clause lines [cl0, cl1], plus its line span.

    Code is DROPPED, not merely skipped over: a fenced block contributes nothing to
    deciding whether a clause is a rule, and rendering the lines between two distant
    prose neighbours would drag the whole snippet back in (measured: one 501-token
    block where 8 prose lines spanned 50 lines of Helm templates). Elided runs are
    marked so the block never reads as contiguous source it is not.

    Backwards: up to CTX_BEFORE prose lines, stopping AT the enclosing heading (kept
    — it is the scope marker). Forwards: up to CTX_AFTER prose lines, stopping at the
    next heading (also kept — it shows the section ending)."""
    def walk(rng, limit):
        """Indices of up to `limit` prose lines, stopping at a heading (kept)."""
        out = []
        for i in rng:
            if mask[i]:
                continue
            out.append(i)
            if len(out) >= limit or _ATX_RE.match(lines[i]):
                break
        return out

    kept = sorted(set(walk(range(cl0 - 1, -1, -1), CTX_BEFORE))
                  | set(range(cl0, cl1 + 1))
                  | set(walk(range(cl1 + 1, len(lines)), CTX_AFTER)))
    # A gap between consecutive kept lines means code (or a skipped run) was
    # dropped there; mark it so the block never reads as contiguous source.
    body = []
    for n, i in enumerate(kept):
        if n and i != kept[n - 1] + 1:
            body.append("    ⋯")
        body.append(lines[i])
    return "\n".join(body), (kept[0] + 1, kept[-1] + 1)


_ATX_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")

# heading_path ("Clean Code > Implementation Checklist") is the cheapest high-value
# signal in the row: ~10 tokens, and it resolves the cases no window can reach when
# the governing heading is 30+ lines up.

DDL = """
CREATE TABLE IF NOT EXISTS rule_clause (
    clause_id       VARCHAR,
    source_file     VARCHAR,
    is_rule         BOOLEAN,
    text            VARCHAR,
    text_sha        VARCHAR,
    char_start      INTEGER,
    char_end        INTEGER,
    context         VARCHAR,
    ctx_start_line  INTEGER,
    ctx_end_line    INTEGER,
    heading_path    VARCHAR,
    "trigger"       VARCHAR,
    trig_assign     VARCHAR,
    enforce         VARCHAR,
    enf_assign      VARCHAR,
    target          VARCHAR,
    tar_assign      VARCHAR,
    spec            VARCHAR
)"""

SCHEMA = pa.schema([
    ("clause_id", pa.string()), ("source_file", pa.string()), ("is_rule", pa.bool_()),
    ("text", pa.string()), ("text_sha", pa.string()),
    ("char_start", pa.int32()), ("char_end", pa.int32()),
    ("context", pa.string()), ("ctx_start_line", pa.int32()), ("ctx_end_line", pa.int32()),
    ("heading_path", pa.string()),
    ("trigger", pa.string()), ("trig_assign", pa.string()),
    ("enforce", pa.string()), ("enf_assign", pa.string()),
    ("target", pa.string()), ("tar_assign", pa.string()),
    ("spec", pa.string()),
])


def md(db=None):
    if not MOTHERDUCK_TOKEN:
        raise RuntimeError("MOTHERDUCK_TOKEN is not set (see .env)")
    return duckdb.connect(f"md:{db or MOTHERDUCK_DB}?motherduck_token={MOTHERDUCK_TOKEN}")


def _sha16(*parts):
    return hashlib.sha256(":".join(str(p) for p in parts).encode()).hexdigest()[:16]


# ── stage 1: download ─────────────────────────────────────────────────────────────────

def download(slice_hex, con=None):
    """One hex slice of deduped, not-yet-extracted files → local/files-<d>.parquet.

    ALWAYS re-queries; never reuses the local file. The anti-join is what makes a re-run
    safe — with no primary key on rule_clause, serving a stale local parquet would
    re-parse and re-insert files that are already loaded, silently duplicating them.
    A slice download is ~50s; correctness is worth more."""
    os.makedirs(LOCAL, exist_ok=True)
    out = os.path.join(LOCAL, f"files-{slice_hex}.parquet")
    own = con is None
    con = con or md()
    t0 = time.time()
    try:
        tbl = con.execute(f"""
            SELECT any_value(file) AS file, content_sha256
            FROM rule_file f
            WHERE length(file) > 0
              AND substr(content_sha256, 1, 1) = '{slice_hex}'
              AND NOT EXISTS (SELECT 1 FROM rule_clause c
                              WHERE c.source_file = f.content_sha256)
            GROUP BY content_sha256
        """).fetch_arrow_table()
    finally:
        if own:
            con.close()
    pq.write_table(tbl, out, compression="zstd")
    return out, tbl.num_rows, time.time() - t0


# ── stage 2: parse (worker) ───────────────────────────────────────────────────────────

def _parse_batch(args):
    """Cut a batch of files into NON-STRUCTURAL clause rows and stage them.

    Each file is parsed inside its own try/except: a ~1-in-2000 document trips an
    IndexError in the grammar, and one bad document must not take a whole batch with it."""
    path, lo, hi, tag = args
    tbl = pq.read_table(path).slice(lo, hi - lo)
    files, shas = tbl.column("file").to_pylist(), tbl.column("content_sha256").to_pylist()
    cid, src, txt, tsha, cs, ce = [], [], [], [], [], []
    ctx, cl0, cl1, hpath = [], [], [], []
    failed = 0
    for content, sha in zip(files, shas):
        content = content or ""
        try:
            units = segment(content)
        except Exception:
            failed += 1
            continue
        offs = _line_offsets(content)
        src_lines = content.split("\n")
        headings = heading_spans(content)
        heading_starts = {h[0] for h in headings}
        fence_mask = _fenced(src_lines)
        for u in units:
            if u["type"] in STRUCTURAL_TYPES:
                continue
            a, b = u["char_start"], u["char_end"]
            cid.append(_sha16(sha, a, b)); src.append(sha)
            txt.append(u["text"])
            tsha.append(hashlib.sha256(_WS.sub(" ", u["text"].strip()).encode()).hexdigest()[:16])
            cs.append(a); ce.append(b)
            body, (lo_ln, hi_ln) = _context(src_lines, fence_mask,
                                            line_of(offs, a) - 1,
                                            line_of(offs, max(a, b - 1)) - 1)
            ctx.append(body)
            cl0.append(lo_ln); cl1.append(hi_ln)
            hpath.append(heading_path_at(headings, a, a in heading_starts))
    n = len(cid)
    null = [None] * n
    out = pa.table({"clause_id": cid, "source_file": src, "is_rule": null,
                    "text": txt, "text_sha": tsha, "char_start": cs, "char_end": ce,
                    "context": ctx, "ctx_start_line": cl0, "ctx_end_line": cl1,
                    "heading_path": hpath,
                    "trigger": null, "trig_assign": null,
                    "enforce": null, "enf_assign": null,
                    "target": null, "tar_assign": null, "spec": null},
                   schema=SCHEMA)
    dest = os.path.join(STAGING, f"clauses-{tag}.parquet")
    pq.write_table(out, dest, compression="zstd")
    return dest, n, failed


def parse(path, workers=WORKERS):
    """Parse a downloaded slice in parallel. Returns (staged_paths, rows, failures)."""
    os.makedirs(STAGING, exist_ok=True)
    total = pq.read_metadata(path).num_rows
    d = os.path.basename(path).split("-")[1].split(".")[0]
    jobs = [(path, lo, min(lo + FILES_PER_BATCH, total), f"{d}-{i:04d}")
            for i, lo in enumerate(range(0, total, FILES_PER_BATCH))]
    if not jobs:
        return [], 0, 0
    with mp.Pool(min(workers, len(jobs))) as p:
        res = p.map(_parse_batch, jobs)
    return [r[0] for r in res], sum(r[1] for r in res), sum(r[2] for r in res)


# ── stage 3: load ─────────────────────────────────────────────────────────────────────

def load(paths=None, con=None):
    """Bulk-load staged parquet into rule_clause. One statement per file = one atomic
    transaction; the staged file is deleted only after it commits."""
    paths = paths or sorted(glob.glob(os.path.join(STAGING, "clauses-*.parquet")))
    if not paths:
        return 0, 0.0
    own = con is None
    con = con or md()
    t0, loaded = time.time(), 0
    try:
        for p in paths:
            n = pq.read_metadata(p).num_rows
            if n:
                con.execute(f"INSERT INTO rule_clause SELECT * FROM read_parquet('{p}')")
            os.remove(p)
            loaded += n
    finally:
        if own:
            con.close()
    return loaded, time.time() - t0


def run_slice(slice_hex, con=None, workers=WORKERS):
    own = con is None
    con = con or md()
    try:
        path, nfiles, dt_d = download(slice_hex, con)
        if not nfiles:
            print(f"[{slice_hex}] nothing to do"); return {}
        t0 = time.time(); staged, rows, failed = parse(path, workers); dt_p = time.time() - t0
        loaded, dt_l = load(staged, con)
        mb = os.path.getsize(path) / 1e6
        print(f"[{slice_hex}] {nfiles:>7,} files ({mb:>6.0f} MB) download {dt_d:>6.1f}s | "
              f"parse {dt_p:>6.1f}s → {rows:>9,} clauses | load {dt_l:>6.1f}s"
              + (f" | {failed} parse failures" if failed else ""))
        return {"slice": slice_hex, "files": nfiles, "rows": rows, "failed": failed,
                "download_s": dt_d, "parse_s": dt_p, "load_s": dt_l, "mb": mb}
    finally:
        if own:
            con.close()


def main():
    ap = argparse.ArgumentParser(description="bulk corpus extraction into rule_clause")
    ap.add_argument("--create-table", action="store_true")
    ap.add_argument("--slice", default=None, help="one hex digit 0-f")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    con = md()
    try:
        if a.create_table:
            con.execute(DDL); print("rule_clause ready")
        if a.status:
            n = con.execute("SELECT count(*) FROM rule_clause").fetchone()[0]
            f = con.execute("SELECT count(DISTINCT source_file) FROM rule_clause").fetchone()[0]
            print(f"rule_clause: {n:,} clauses from {f:,} files")
        todo = [a.slice] if a.slice else (list(SLICES) if a.all else [])
        agg = []
        t0 = time.time()
        for s in todo:
            agg.append(run_slice(s, con, a.workers))
        if len(todo) > 1:
            g = [x for x in agg if x]
            print(f"\ntotal: {sum(x['files'] for x in g):,} files → "
                  f"{sum(x['rows'] for x in g):,} clauses in {time.time()-t0:.0f}s")
    finally:
        con.close()


if __name__ == "__main__":
    main()
