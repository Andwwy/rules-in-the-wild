"""Hugging Face I/O: read the rule files, insert the clauses.

Read side  — `read_files()` pulls the `files` config (data/*.parquet) off the Hub.
Write side — `insert_clauses()` / `insert_clause()` commit rows into the `clauses`
             config (clauses/*.parquet) of the same dataset repo.

The write is a read-modify-write of the whole `clauses` folder committed atomically:
existing shards are read, merged with the incoming rows under the chosen mode, and
written back as freshly consolidated shards in ONE commit (adds + deletes together).
That buys two things a naive append cannot — the config never holds duplicate
clause_ids, and it never keeps clauses from a file revision that no longer exists.

Nothing here writes to the `files` config; the corpus is read-only to this project.
"""
import os
import tempfile

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi, hf_hub_download
from huggingface_hub.errors import EntryNotFoundError, RepositoryNotFoundError

from .config import (CLAUSES_DIR, FILES_DIR, HF_REPO_ID, HF_REVISION, HF_TOKEN,
                     MAX_ROWS_PER_SHARD)
from .schema import CLAUSE_SCHEMA, COLUMNS, EXTRACTION_KEY, to_table

MODES = ("sync", "append", "replace")


def _api(token=None):
    return HfApi(token=token or HF_TOKEN)


def _shards(repo_id, folder, token=None, revision=None):
    """Parquet shards under `folder/`, sorted for deterministic order."""
    try:
        files = _api(token).list_repo_files(repo_id, repo_type="dataset",
                                            revision=revision or HF_REVISION)
    except RepositoryNotFoundError:
        raise RuntimeError(f"dataset '{repo_id}' not found (or private to this token)")
    prefix = folder.rstrip("/") + "/"
    return sorted(f for f in files if f.startswith(prefix) and f.endswith(".parquet"))


def _read_folder(repo_id, folder, token=None, revision=None, schema=None, columns=None):
    paths = _shards(repo_id, folder, token, revision)
    tables = []
    for p in paths:
        local = hf_hub_download(repo_id, p, repo_type="dataset",
                                revision=revision or HF_REVISION, token=token or HF_TOKEN)
        tables.append(pq.read_table(local, columns=columns))
    if not tables:
        return schema.empty_table() if schema is not None else None
    return tables[0] if len(tables) == 1 else pa.concat_tables(tables, promote_options="default")


# ── read side ─────────────────────────────────────────────────────────────────────────

def read_files(repo_id=None, token=None, revision=None, limit=0, local=None):
    """The rule_file corpus as a pyarrow Table. Only repo, path, content_sha256 and the
    text column are required of it.

    `local` reads a parquet file or directory from disk instead of the Hub — for offline
    runs and for cutting a corpus that has not been uploaded yet."""
    if local:
        t = pq.read_table(local)
        return t.slice(0, limit) if limit else t
    t = _read_folder(repo_id or HF_REPO_ID, FILES_DIR, token, revision)
    if t is None:
        raise RuntimeError(
            f"no parquet files under '{FILES_DIR}/' in {repo_id or HF_REPO_ID} — "
            "is HF_FILES_DIR pointing at the right folder?")
    return t.slice(0, limit) if limit else t


def read_clauses(repo_id=None, token=None, revision=None, columns=None):
    """The clauses config — empty (but correctly typed) before the first push."""
    return _read_folder(repo_id or HF_REPO_ID, CLAUSES_DIR, token, revision,
                        schema=CLAUSE_SCHEMA, columns=columns)


def extracted_index(repo_id=None, token=None, revision=None, clauses=None):
    """{(file_id, content_sha256, grammar, parser_version)} already on the Hub.

    The "already extracted?" check, answered from the clause data itself — there is no
    side table of crawl state to drift out of sync. Only the key columns are downloaded,
    never the clause text."""
    t = clauses if clauses is not None else read_clauses(repo_id, token, revision,
                                                         columns=list(EXTRACTION_KEY))
    if not t.num_rows:
        return set()
    return set(zip(*[t.column(c).to_pylist() for c in EXTRACTION_KEY]))


# ── write side ────────────────────────────────────────────────────────────────────────

def _merge(existing, incoming, mode):
    """Combine the Hub's current clauses with the incoming ones. Returns (table, stats)."""
    if mode not in MODES:
        raise ValueError(f"unknown mode '{mode}' (expected one of {', '.join(MODES)})")
    if mode == "replace" or existing.num_rows == 0:
        kept = existing.slice(0, 0)
        replaced = existing.num_rows if mode == "replace" else 0
        added = incoming
    elif mode == "append":
        have = set(existing.column("clause_id").to_pylist())
        mask = [cid not in have for cid in incoming.column("clause_id").to_pylist()]
        kept, replaced = existing, 0
        added = incoming.filter(pa.array(mask, type=pa.bool_()))
    else:   # sync — the incoming set is authoritative for the files it covers
        touched = pc.is_in(existing.column("file_id"),
                           value_set=incoming.column("file_id").unique())
        kept = existing.filter(pc.invert(touched))
        replaced = existing.num_rows - kept.num_rows
        added = incoming
    out = pa.concat_tables([kept, added]) if kept.num_rows else added
    # Reading order: file, then position within it — the dataset viewer and any sequential
    # read then follow the document, and shard boundaries stay stable across runs.
    if out.num_rows:
        out = out.sort_by([("repo", "ascending"), ("path", "ascending"), ("idx", "ascending")])
    return out, {"kept": kept.num_rows, "replaced": replaced, "added": added.num_rows,
                 "total": out.num_rows}


def _write_shards(table, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    written, n = [], max(1, MAX_ROWS_PER_SHARD)
    total = max(table.num_rows, 1)      # always write at least one (possibly empty) shard
    for i, start in enumerate(range(0, total, n)):
        name = f"part-{i:05d}.parquet"
        local = os.path.join(out_dir, name)
        pq.write_table(table.slice(start, n), local, compression="zstd")
        written.append((name, local))
    return written


def insert_clauses(rows, repo_id=None, token=None, revision=None, mode="sync",
                   commit_message=None, dry_run=False, out_dir=None):
    """Insert clause rows into the dataset's `clauses` config. THE write endpoint.

    mode  "sync"    incoming rows are authoritative for the files they cover: every
                    stored clause of those file_ids is replaced. This is what removes
                    clauses belonging to a superseded file revision.
          "append"  keep everything, add only clause_ids not already stored.
          "replace" the incoming rows become the entire clauses config.

    dry_run builds and validates everything and writes the parquet locally, committing
    nothing. Returns a stats dict."""
    repo_id = repo_id or HF_REPO_ID
    incoming = rows if isinstance(rows, pa.Table) else to_table(rows)
    if incoming.schema != CLAUSE_SCHEMA:
        incoming = incoming.select(COLUMNS).cast(CLAUSE_SCHEMA)

    existing = read_clauses(repo_id, token, revision)
    merged, stats = _merge(existing, incoming, mode)
    stats.update(incoming=incoming.num_rows, mode=mode,
                 files=len(set(incoming.column("file_id").to_pylist())))

    tmp = out_dir or tempfile.mkdtemp(prefix="clauses_")
    shards = _write_shards(merged, tmp)
    stats["shards"] = [n for n, _ in shards]
    stats["local_dir"] = tmp

    if dry_run:
        stats["commit_url"] = None
        return stats

    if not (token or HF_TOKEN):
        raise RuntimeError("HF_TOKEN is not set — a write-scoped token is required to "
                           "push (put HF_TOKEN=... in .env or export it).")
    new_names = {f"{CLAUSES_DIR}/{n}" for n, _ in shards}
    ops = [CommitOperationAdd(path_in_repo=f"{CLAUSES_DIR}/{n}", path_or_fileobj=p)
           for n, p in shards]
    ops += [CommitOperationDelete(path_in_repo=p)
            for p in _shards(repo_id, CLAUSES_DIR, token, revision) if p not in new_names]
    info = _api(token).create_commit(
        repo_id=repo_id, repo_type="dataset", revision=revision or HF_REVISION,
        operations=ops,
        commit_message=commit_message or
        f"clauses: {mode} {stats['added']} rows from {stats['files']} files "
        f"({merged.num_rows} total)")
    stats["commit_url"] = getattr(info, "commit_url", None)
    return stats


def insert_clause(clause, repo_id=None, token=None, revision=None, mode="append", **kw):
    """Insert ONE clause. Defaults to `append` so a single-row call can never wipe the
    rest of that file's clauses."""
    return insert_clauses([clause], repo_id=repo_id, token=token, revision=revision,
                          mode=mode, **kw)


# ── dataset card ──────────────────────────────────────────────────────────────────────

_CARD = """---
configs:
- config_name: files
  default: true
  data_files:
  - split: train
    path: {files_dir}/*.parquet
- config_name: clauses
  data_files:
  - split: train
    path: {clauses_dir}/*.parquet
---

# rules

Natural-language rules written for LLM coding agents, and the individual clauses cut out
of them by a deterministic markdown grammar.

| config | one row per |
|--------|-------------|
| `files` (default) | a rule file discovered in a public repository |
| `clauses` | one clause inside such a file |

```python
from datasets import load_dataset

files   = load_dataset("{repo_id}", "files",   split="train")
clauses = load_dataset("{repo_id}", "clauses", split="train")
```

## How clauses are produced

A markdown grammar supplies the block skeleton — headings, list items, paragraphs, code
fences, tables, YAML front matter — and paragraphs are then split at sentence
boundaries. Each clause carries exact character and line offsets into its source file,
so `clause_text == file[char_start:char_end]` always holds.

The segmentation is deterministic: the same file content always yields the same clauses
with the same ids. No model decides what is or is not a rule — `unit_type` records what
each unit structurally is (`statement`, `clause`, `table_row`, `field`, `heading`,
`code`, `table_header`) and `is_structural` flags the skeleton, so you filter for the
granularity you want.

`clause_id` is versioned by file content, so clauses from a superseded revision are
replaced rather than accumulated. `text_sha256` hashes the whitespace-normalized wording,
so the same rule copied across repositories groups with a `GROUP BY`.
"""


def dataset_card(repo_id=None):
    """The README that declares both configs. Without it the Hub auto-detects the split
    layout and a second parquet folder confuses it."""
    repo_id = repo_id or HF_REPO_ID
    return _CARD.format(files_dir=FILES_DIR, clauses_dir=CLAUSES_DIR, repo_id=repo_id)


def push_dataset_card(repo_id=None, token=None, revision=None, dry_run=False, force=False):
    """Write that README. Refuses to clobber an existing card unless `force` — the card
    is human-authored content on a public page."""
    repo_id = repo_id or HF_REPO_ID
    try:
        hf_hub_download(repo_id, "README.md", repo_type="dataset",
                        revision=revision or HF_REVISION, token=token or HF_TOKEN)
        exists = True
    except EntryNotFoundError:
        exists = False
    if exists and not force:
        return {"written": False, "reason": "README.md already exists (pass --force-card)"}
    card = dataset_card(repo_id)
    if dry_run:
        return {"written": False, "reason": "dry run", "card": card}
    _api(token).upload_file(path_or_fileobj=card.encode("utf-8"), path_in_repo="README.md",
                            repo_id=repo_id, repo_type="dataset",
                            revision=revision or HF_REVISION,
                            commit_message="Declare files/clauses configs")
    return {"written": True, "card": card}


__all__ = ["read_files", "read_clauses", "extracted_index", "insert_clauses",
           "insert_clause", "dataset_card", "push_dataset_card", "MODES"]
