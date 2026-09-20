"""clause_extraction — rule files in, individual clauses out.

    Andwwy/rules                                        Andwwy/rules
     config "files"  ──►  deterministic grammar  ──►      config "clauses"
     data/*.parquet       (markdown, no LLM)              clauses/*.parquet

One job: cut the natural-language rule files that people write for LLM coding agents
into individual clauses, deterministically. No model, no labelling, no judgement about
what counts as a rule — just reproducible segmentation with exact character offsets.

    grammar.py   THE parser: where a clause starts and ends (see GRAMMAR.md)
    extract.py   one file row -> its clause rows
    schema.py    the clause schema written to Hugging Face
    hub.py       read the files config, insert into the clauses config
    run.py       the CLI

    python -m clause_extraction.run --help
"""
from .grammar import segment, GRAMMARS, DEFAULT_GRAMMAR   # noqa: F401

__all__ = ["segment", "GRAMMARS", "DEFAULT_GRAMMAR"]
