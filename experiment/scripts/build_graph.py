"""Write the toolbox's graph.json from its node files, and check the graph (design_process.md, point 72).

    python3 scripts/build_graph.py

Nodes: one file per leaf of the enforcer, trigger and target trees (container/toolbox/{enforcers,triggers,targets}/),
the mechanisms (mechanisms/*.md), the skeletons (skeletons/*) and the recipes (`enforce install`). Edges: the links in a
node file (absolute container paths, /opt/enforce-toolbox/…), labelled by the line they are on (`before`, `check`,
`nearest`, …), and `install: <recipe>`. Fails if a link does not resolve, or a leaf of a tree has no node.
"""
from __future__ import annotations

import json
import re
import sys

import paths

T = "/opt/enforce-toolbox"
TB = paths.TOOLBOX
TREES = {"enforcers": "enforcer", "triggers": "trigger", "targets": "target"}
JEV_TREES = {"enforcers": "enforcer-tree-simple.json", "triggers": "trigger-tree.json", "targets": "target-tree.json"}


def slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def leaf_file(tree: str, path: str) -> str:
    return f"{tree}/" + "/".join(slug(p) for p in path.split(" › ")) + ".md"


def tree_leaves(tree: str) -> list[str]:
    """Every leaf path of Jev's tree for this axis (rules in the wild/jev mapping/), below its root."""
    data = json.loads((paths.RITW / "jev mapping" / JEV_TREES[tree]).read_text(encoding="utf-8"))
    data.pop("descriptions", None)
    out = []

    def walk(node, prefix):
        for x in node:
            if isinstance(x, str):
                out.append(" › ".join(prefix + [x]))
            else:
                for name, kids in x.items():
                    walk(kids, prefix + [name])
    walk(next(iter(data.values())), [])
    return out


def main() -> int:
    sys.path.insert(0, str(TB))
    from enforce_lib.recipes import RECIPES
    nodes, edges, problems = [], [], []
    for name, r in RECIPES.items():
        nodes.append({"id": f"recipe:{name}", "kind": "recipe", "title": r["about"]})
    for f in sorted(f for f in (TB / "skeletons").iterdir() if f.is_file() and f.name != ".DS_Store"):
        nodes.append({"id": f"skeletons/{f.name}", "kind": "skeleton", "title": f.name})
    files = sorted(p for d in (*TREES, "mechanisms") for p in (TB / d).rglob("*.md"))
    for f in files:
        rel = str(f.relative_to(TB))
        lines = f.read_text(encoding="utf-8").splitlines()
        kind = "mechanism" if rel.startswith("mechanisms/") else TREES[rel.split("/")[0]]
        nodes.append({"id": rel, "kind": kind, "title": lines[0].lstrip("# ").strip()})
        for line in lines:
            label = (re.match(r"- ([\w ]+):", line) or re.match(r"(From the leaf's note)", line) or [None, ""])[1]
            for link in re.findall(rf"{T}/[^\s),;]+", line):
                target = link[len(T) + 1:]
                if not (TB / target).exists():
                    problems.append(f"{rel}: the link {link} does not resolve")
                edges.append({"from": rel, "to": target, "label": label})
            for recipe in re.findall(r"`enforce install ([\w-]+)`|install: `([\w-]+)`(?:, `([\w-]+)`)?", line):
                for name in filter(None, recipe):
                    if name not in RECIPES:
                        problems.append(f"{rel}: no recipe {name!r}")
                    edges.append({"from": rel, "to": f"recipe:{name}", "label": "install"})
    for tree in TREES:
        leaves = tree_leaves(tree)                      # Jev can route to every leaf of its tree
        for path in leaves:
            if not (TB / leaf_file(tree, path)).exists():
                problems.append(f"no node for the {TREES[tree]} leaf {path} ({leaf_file(tree, path)})")
        for f in (TB / tree).rglob("*.md"):
            if f.read_text(encoding="utf-8").split("\n", 1)[0].lstrip("# ").strip() not in leaves:
                problems.append(f"{f.relative_to(TB)}: its first line names no leaf of the {TREES[tree]} tree")
    (TB / "graph.json").write_text(json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False, indent=1) + "\n",
                                   encoding="utf-8")
    kinds = {k: sum(n["kind"] == k for n in nodes) for k in ("enforcer", "trigger", "target", "mechanism", "skeleton", "recipe")}
    print(f"graph.json: {len(nodes)} nodes {kinds}, {len(edges)} edges")
    for p in problems:
        print(f"  ✗ {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
