"""Dedup-threshold and model constants used by cluster.py, judge.py, embedder.py,
and admin_app.py.

TODO(cluster-calibration, week-2):
    The cluster thresholds are PLACEHOLDER values — see DESIGN.md §8.
    After the calibration session, update CLUSTER_THRESHOLD in this file AND
    the matching comment block in ../Design docs/schema.sql AND the §8 bullet
    in ../Design docs/DESIGN.md. The three-places-in-sync rule.

Pre-prod swap:
    EMBEDDING_MODEL currently points at Perplexity's 0.6b embedder so the
    prototype runs with a single API key. DESIGN.md specs `voyage-3` in
    production. Both are 1024-d, so the schema column doesn't move.
"""

# ≥ CLUSTER_THRESHOLD cosine → same rule_cluster, suggested labels propagate
CLUSTER_THRESHOLD: float = 0.93

# SEE_ALSO_FLOOR ≤ cosine < CLUSTER_THRESHOLD → rule_related sidebar, no propagation
SEE_ALSO_FLOOR: float = 0.80

# Trigram similarity above this attaches a rule to an existing cluster directly
# (cheaper than embedding lookup; runs before pgvector NN search).
TRIGRAM_ATTACH: float = 0.85

# Embedding model. Must produce a 1024-d vector to fit rule.embedding's column.
# PROTOTYPE: Perplexity `pplx-embed-v1-0.6b`. PROD: "voyage-3".
EMBEDDING_MODEL = "pplx-embed-v1-0.6b"

# Judge model, routed via Perplexity Agent API (no markup over Anthropic direct).
JUDGE_MODEL = "anthropic/claude-haiku-4-5"
JUDGE_PROMPT_VERSION = "v1"

# Set False to skip judge calls during ingest (rules are still stored,
# rule_llm_decision rows are simply not written). Saves API spend while iterating
# on extractor/embedder. Flip back to True when ready to label.
JUDGE_ENABLED = False
