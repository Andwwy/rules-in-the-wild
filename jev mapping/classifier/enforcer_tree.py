"""Map a rule onto the enforcer decision tree (`../enforcer-tree-simple.json`) with TypeSafe Jev.

    python enforcer_tree.py "Every function name must follow snake_case"
    python enforcer_tree.py "…" --context '{"mtac_category": "Style / Naming"}'

    from enforcer_tree import classify           # (add this folder to sys.path)
    result = classify(rule_text, context={...})   # → {"leaf", "path", "score", "separation", "alternatives", ...}

The enforcer axis of `tree_classifier.py`, under the names that the MTAC scripts import (`TREE`, `load_tree`, `_client`,
`classify`). The method, the prompt and the output are those of `tree_classifier.py` with axis "enforcer".
"""
from __future__ import annotations

import argparse
import json

from tree_classifier import AXES, BEAM, MODEL, Node, _client  # noqa: F401
from tree_classifier import classify as _classify, load_tree as _load_tree

TREE = AXES["enforcer"].tree


def load_tree(path=TREE) -> Node:
    return _load_tree(path)


def classify(rule: str, context: dict | None = None, *, tree: Node | None = None, client=None,
             beam: int = BEAM) -> dict:
    return _classify("enforcer", rule, context, tree=tree, client=client, beam=beam)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("rule")
    p.add_argument("--context", type=json.loads, help="JSON object sent with the rule as `context`")
    p.add_argument("--beam", type=int, default=BEAM)
    args = p.parse_args()
    print(json.dumps(classify(args.rule, args.context, beam=args.beam), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
