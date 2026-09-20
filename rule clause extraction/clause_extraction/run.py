"""The pipeline run: rule files → clauses → back to the Hub.

    python -m clause_extraction.run                    # DRY RUN: cut, report, write nothing
    python -m clause_extraction.run --push             # commit the clauses config
    python -m clause_extraction.run --grammar v1       # cut with the legacy grammar
    python -m clause_extraction.run --refresh --push   # re-cut everything (after a grammar change)
    python -m clause_extraction.run --compare          # v1 vs v2 defect counts, writes nothing
    python -m clause_extraction.run --stats            # what is on the Hub
    python -m clause_extraction.run --schema           # the clause schema

Pushing is opt-in because the target is a PUBLIC dataset: a run with no flags never
mutates the Hub.

"Compare if already cut, if not cut": a file is skipped when the clauses config already
holds rows for its (file_id, content_sha256, grammar, parser_version). Change the file's
content — or the grammar, or PARSER_VERSION — and it is cut again, its superseded rows
replaced rather than duplicated by the `sync` insert.
"""
import argparse
import datetime as _dt
import re
import time

from .config import (GRAMMAR, FILES_TEXT_COLUMN, HF_REPO_ID, HF_TOKEN, PARSER_VERSION,
                     MOTHERDUCK_DB, MD_FILES_TABLE)
from .extract import extract_clauses, skip_reason
from .grammar import GRAMMARS, STRUCTURAL_TYPES, segment
from .hub import (extracted_index, insert_clauses, push_dataset_card, read_clauses,
                  read_files)
from .schema import EXTRACTION_KEY, describe, make_file_id


def _now_id():
    return "run_" + _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d_%H%M%S")


def _rows_of(table):
    """Iterate a pyarrow Table as dicts without materializing the whole corpus."""
    for batch in table.to_batches(max_chunksize=64):
        yield from batch.to_pylist()


def _source_label(files_local, md, md_where):
    if md:
        return f"motherduck:{MOTHERDUCK_DB}.{MD_FILES_TABLE}" + (f" WHERE {md_where}" if md_where else "")
    return files_local or "hub"


def run(repo_id=None, limit=0, refresh=False, push=False, mode="sync", out_dir=None,
        token=None, revision=None, files_local=None, grammar=None,
        motherduck=False, md_where=None, md_db=None, md_table=None):
    repo_id = repo_id or HF_REPO_ID
    grammar = grammar or GRAMMAR
    run_id = _now_id()
    stamp = _dt.datetime.now(_dt.timezone.utc)

    print(f"\n=== clause_extraction {run_id} ===")
    print(f"dataset: {repo_id}   {'PUSH' if push else 'DRY-RUN'}"
          f"{'  +refresh' if refresh else ''}")
    print(f"grammar: {grammar} (parser {PARSER_VERSION})")
    print(f"files:   {_source_label(files_local, motherduck, md_where)}\n")

    if motherduck:
        from .motherduck import read_files as md_read
        files = md_read(db=md_db, table=md_table, where=md_where, limit=limit)
    else:
        files = read_files(repo_id, token, revision, limit=limit, local=files_local)
    if FILES_TEXT_COLUMN not in files.column_names:
        raise RuntimeError(
            f"the files config has no '{FILES_TEXT_COLUMN}' column (found: "
            f"{', '.join(files.column_names)}) — set HF_FILES_TEXT_COLUMN.")
    src = "in MotherDuck" if motherduck else ("on disk" if files_local else "on the Hub")
    print(f"[files] {files.num_rows} rule files {src}")

    done = set() if refresh else extracted_index(repo_id, token, revision)
    if done:
        print(f"[clauses] {len(done)} file revisions already cut")

    rows, seen, skipped, cut, reasons = [], 0, 0, 0, []
    for f in _rows_of(files):
        seen += 1
        why = skip_reason(f)
        if why:
            skipped += 1
            if len(reasons) < 10:
                reasons.append(f"{f.get('repo')}:{f.get('path')}: {why}")
            continue
        key = (make_file_id(f.get("repo"), f.get("path")), f.get("content_sha256"),
               grammar, PARSER_VERSION)
        if key in done:
            skipped += 1
            continue
        new = extract_clauses(f, run_id, grammar=grammar, extracted_at=stamp)
        if not new:
            skipped += 1
            if len(reasons) < 10:
                reasons.append(f"{f.get('repo')}:{f.get('path')}: no parseable units")
            continue
        rows.extend(new)
        cut += 1

    print(f"[cut]   files seen={seen} cut={cut} skipped={skipped}  |  clauses={len(rows)}")
    for r in reasons:
        print("   -", r)

    if not rows:
        print("\nnothing new to insert.")
        return {"run_id": run_id, "files": seen, "cut": 0, "clauses": 0}

    stats = insert_clauses(rows, repo_id=repo_id, token=token, revision=revision,
                           mode=mode, dry_run=not push, out_dir=out_dir,
                           commit_message=f"{run_id}: {len(rows)} clauses from {cut} files "
                                          f"(grammar {grammar})")
    print(f"\n[insert] mode={stats['mode']} incoming={stats['incoming']} "
          f"added={stats['added']} replaced={stats['replaced']} kept={stats['kept']} "
          f"→ {stats['total']} clauses in {len(stats['shards'])} shard(s)")
    print(f"[insert] parquet: {stats['local_dir']}")
    if stats.get("commit_url"):
        print(f"[insert] committed: {stats['commit_url']}")
    else:
        print("[insert] DRY RUN — nothing written to the Hub (pass --push to commit)")

    return {"run_id": run_id, "files": seen, "cut": cut, "clauses": len(rows), **stats}


def stats(repo_id=None, token=None, revision=None):
    repo_id = repo_id or HF_REPO_ID
    try:
        files = read_files(repo_id, token, revision)
        files_err = None
    except RuntimeError as e:
        files, files_err = None, str(e)
    clauses = read_clauses(repo_id, token, revision)
    print(f"\n=== {repo_id} ===")
    print(f"files   : {files_err or f'{files.num_rows} rows, columns: ' + ', '.join(files.column_names)}")
    print(f"clauses : {clauses.num_rows} rows")
    if clauses.num_rows:
        import pyarrow.compute as pc
        n_files = len(set(clauses.column("file_id").to_pylist()))
        uniq = len(set(clauses.column("text_sha256").to_pylist()))
        gr = sorted(set(clauses.column("grammar").to_pylist()))
        print(f"          from {n_files} files | {uniq} distinct wordings | grammar {', '.join(gr)}")
        types = pc.value_counts(clauses.column("unit_type").combine_chunks())
        print("          unit_type: " + ", ".join(
            f"{d['values']}={d['counts']}" for d in types.to_pylist()))
    return files, clauses


def compare(repo_id=None, token=None, revision=None, files_local=None, limit=0):
    """Cut the corpus with BOTH grammars and report the defect counts side by side.
    Writes nothing — this is the instrument for judging a grammar change."""
    files = read_files(repo_id, token, revision, limit=limit, local=files_local)
    def defects(units):
        mid = frag = 0
        for a, b in zip(units, units[1:]):
            ta, tb = a["text"].strip(), b["text"].strip()
            if a["type"] in ("clause", "prose", "statement") \
               and not re.search(r'[.!?;:)`"|\]]$', ta) and re.match(r"^[a-z]", tb):
                mid += 1
        for u in units:
            if u["type"] not in STRUCTURAL_TYPES and len(u["text"].split()) <= 3:
                frag += 1
        return mid, frag
    agg = {g: [0, 0, 0] for g in GRAMMARS}     # units, mid-sentence breaks, fragments
    for f in _rows_of(files):
        content = f.get(FILES_TEXT_COLUMN) or ""
        for g in GRAMMARS:
            u = segment(content, g)
            mid, frag = defects(u)
            agg[g][0] += len(u); agg[g][1] += mid; agg[g][2] += frag
    print(f"\n{'':<28}" + "".join(f"{g:>10}" for g in GRAMMARS))
    for i, lab in enumerate(("total units", "mid-sentence breaks", "≤3-word fragments")):
        print(f"{lab:<28}" + "".join(f"{agg[g][i]:>10}" for g in GRAMMARS))
    return agg


def main():
    ap = argparse.ArgumentParser(description="rule files → deterministic clause extraction → Hugging Face")
    ap.add_argument("--repo", default=None, help=f"dataset repo id (default {HF_REPO_ID})")
    ap.add_argument("--grammar", default=None, choices=GRAMMARS,
                    help=f"segmentation grammar (default {GRAMMAR})")
    ap.add_argument("--limit", type=int, default=0, help="only process the first N rule files")
    ap.add_argument("--refresh", action="store_true", help="re-cut every file, even ones already done")
    ap.add_argument("--push", action="store_true", help="COMMIT to the Hub (default: dry run)")
    ap.add_argument("--mode", default="sync", choices=("sync", "append", "replace"),
                    help="insert mode (default sync)")
    ap.add_argument("--out", default=None, help="directory for the generated parquet")
    ap.add_argument("--files-parquet", default=None,
                    help="read the rule files from local parquet instead of the Hub")
    ap.add_argument("--motherduck", action="store_true",
                    help="read the rule files from MotherDuck instead of the Hub")
    ap.add_argument("--md-db", default=None, help=f"MotherDuck database (default {MOTHERDUCK_DB})")
    ap.add_argument("--md-table", default=None, help=f"files table (default {MD_FILES_TABLE})")
    ap.add_argument("--md-where", default=None,
                    help="raw SQL WHERE clause to scope the MotherDuck read")
    ap.add_argument("--md-probe", action="store_true",
                    help="check the MotherDuck connection + schema mapping, then exit")
    ap.add_argument("--revision", default=None, help="dataset branch (default main)")
    ap.add_argument("--stats", action="store_true", help="report Hub state and exit")
    ap.add_argument("--schema", action="store_true", help="print the clause schema and exit")
    ap.add_argument("--compare", action="store_true", help="v1 vs v2 defect counts, then exit")
    ap.add_argument("--push-card", action="store_true", help="write the README declaring the configs")
    ap.add_argument("--force-card", action="store_true", help="overwrite an existing README")
    args = ap.parse_args()

    if args.schema:
        print("\nclause schema (config 'clauses'):\n" + describe())
        print("\nalready-cut key: " + ", ".join(EXTRACTION_KEY))
        return
    if args.stats:
        stats(args.repo, revision=args.revision)
        return
    if args.md_probe:
        from .motherduck import probe
        from .config import MD_COLUMNS
        info = probe(db=args.md_db, table=args.md_table)
        print(f"\nMotherDuck OK — database '{info['database']}'")
        print(f"  tables: {', '.join(info['tables']) or '(none)'}")
        print(f"  files table '{info['files_table']}': "
              + (f"{info['rows']:,} rows" if info["present"] else "NOT FOUND"))
        if info.get("present"):
            print(f"  columns: {', '.join(info['columns'])}")
            print("  mapping:")
            for canon, src in MD_COLUMNS.items():
                mark = "ok " if (src and src in info["columns"]) else ("-- " if not src else "MISSING")
                print(f"    {mark} {canon:<16} <- {src or '(defaulted)'}")
            if info["unmapped"]:
                print("  ⚠ unmapped: " + ", ".join(info["unmapped"]))
        return
    if args.compare:
        compare(args.repo, revision=args.revision, files_local=args.files_parquet,
                limit=args.limit)
        return
    if args.push_card:
        res = push_dataset_card(args.repo, revision=args.revision, dry_run=not args.push,
                                force=args.force_card)
        print(res.get("reason") or "README.md written")
        if not res["written"] and res.get("card"):
            print("\n--- card ---\n" + res["card"])
        return

    if args.push and not HF_TOKEN:
        ap.error("--push needs a write-scoped HF_TOKEN (put it in .env or export it)")

    t0 = time.time()
    run(args.repo, limit=args.limit, refresh=args.refresh, push=args.push, mode=args.mode,
        out_dir=args.out, revision=args.revision, files_local=args.files_parquet,
        grammar=args.grammar, motherduck=args.motherduck, md_where=args.md_where,
        md_db=args.md_db, md_table=args.md_table)
    print(f"\ndone in {time.time() - t0:.1f}s")


def _cli():
    """main() with clean, single-line reporting for configuration errors — a missing
    token should not greet you with a traceback."""
    try:
        main()
    except RuntimeError as e:
        raise SystemExit(f"error: {e}")


if __name__ == "__main__":
    _cli()
