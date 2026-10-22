"""Build the page of the policy mapping: where the rules landed, and the whole decision tree they were mapped onto.

    python scripts/ring.py        → tasks/mapping ring.html (open it in a browser)

Reads `mapping` from tasks/<task>/rules.json (written by map_rules.py) and the tree from
`rules in the wild/jev mapping/enforcer-tree-simple.json`.

    Mapping result     ring sized by rules: only the classes that rules reached
    Decision classes   ring sized by leaves: every class of the tree; reached classes in colour, the rest grey;
                       plus the tree as an outline with each class's rule count

Each top-level class keeps one colour in both rings. The rings and the rule table are plain SVG/HTML, so the page shows
without scripts; a short script only filters the table when a segment or an outline entry is clicked.
"""
from __future__ import annotations

import html
import json
import math
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
import paths                                      # noqa: E402

paths.use("jev")
from enforcer_tree import TREE, load_tree                  # noqa: E402

OUT = paths.TASKS / "mapping ring.html"
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
OTHER_COLOR = "#8a8f8c"
R_IN, R_OUT = 64, 195

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Policy Mapping Ring</title>
<style>
:root{--bg:#f7f7f5;--fg:#1d1f1e;--muted:#6b706d;--line:#e2e3df;--warn:#a5600a;--empty:#dcddd9}
@media (prefers-color-scheme:dark){:root{--bg:#151716;--fg:#e8e9e6;--muted:#9a9f9b;--line:#2c2f2d;--warn:#e3a54a;--empty:#333634}}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,-apple-system,"PingFang SC",sans-serif}
.page{max-width:1100px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:20px;font-weight:600;margin:0 0 4px}
h2{font-size:16px;font-weight:600;margin:34px 0 4px}
.sub{color:var(--muted);margin:0 0 14px}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;margin-bottom:14px;font-size:13px;color:var(--muted)}
.sw{width:10px;height:10px;border-radius:2px;display:inline-block;margin-right:5px;vertical-align:-1px}
.wrap{display:grid;grid-template-columns:minmax(0,420px) minmax(0,1fr);gap:28px;align-items:start}
@media (max-width:760px){.wrap{grid-template-columns:minmax(0,1fr)}}
svg .seg{cursor:pointer;stroke:var(--bg);stroke-width:1.5}
svg .seg:hover{opacity:.82}
svg text{pointer-events:none}
.head{font-size:16px;font-weight:600;margin:0 0 2px}
.meta{color:var(--muted);font-size:12.5px;margin:0 0 10px}
table{width:100%;border-collapse:collapse;font-size:13px}
td{border-top:1px solid var(--line);padding:7px 6px;vertical-align:top}
.id,.num{color:var(--muted);font-size:12px;font-variant-numeric:tabular-nums;white-space:nowrap}
.num{text-align:right}
.cat{color:var(--muted);font-size:12px}
.low{color:var(--warn)}
.tree,.tree ul{list-style:none;margin:0;padding-left:16px}
.tree{padding-left:0;font-size:13px;columns:2;column-gap:24px}
@media (max-width:760px){.tree{columns:1}}
.tree li{break-inside:avoid;padding:1px 0}
.tree .n{cursor:pointer}
.tree .n:hover{text-decoration:underline}
.tree .c{font-variant-numeric:tabular-nums;font-weight:600;margin-left:4px}
.tree .z{color:var(--muted)}
</style></head><body><div class="page">
<h1>Policy mapping ring</h1>
<p class="sub">__N__ policy rules of MTAC tasks __TASKS__, mapped by Jev onto <code>enforcer-tree-simple.json</code>.
Click a segment or a class to list only its rules; click a ring's centre to list all.</p>
<p class="sub"><b>Translated from Mandarin.</b> MTAC's rules are written in Mandarin Chinese; the rule texts below are English
translations. Literal strings that a rule requires stay in Chinese, with the meaning in brackets. Hover a rule to see the
original; the originals are also in each task's <code>rules.json</code>. Jev mapped the original texts.</p>

<h2>Mapping result</h2>
<p class="sub">Sized by rules: only the classes that rules reached.</p>
<div class="legend">__LEGEND__</div>
<div class="wrap">
<svg viewBox="-200 -200 400 400" width="100%" role="img" aria-label="Ring of the rules by enforcer-tree path">
__RESULT__
</svg>
<div><p class="head" id="head">All mapped rules</p><p class="meta" id="meta">__N__ rules · __LOW__ close calls (separation under 1.2)</p>
<table><tbody id="rows">
__ROWS__
</tbody></table></div>
</div>

<h2>Decision classes</h2>
<p class="sub">The whole tree, sized by its __LEAVES__ leaf classes. Classes that rules reached are in colour; the others are grey.
__REACHED__ of __LEAVES__ leaf classes hold a rule.</p>
<div class="wrap">
<svg viewBox="-200 -200 400 400" width="100%" role="img" aria-label="Ring of every class in the enforcer tree">
__CLASSES__
</svg>
<ul class="tree">__OUTLINE__</ul>
</div>
</div>
<script>
const rows=[...document.querySelectorAll("#rows tr")];
function filter(p){let n=0,low=0;
  rows.forEach(r=>{const on=!p||r.dataset.path===p||r.dataset.path.startsWith(p+" > ");r.hidden=!on;if(on){n++;if(r.dataset.low)low++;}});
  document.getElementById("head").textContent=p||"All mapped rules";
  document.getElementById("meta").textContent=n+" rules · "+low+" close calls (separation under 1.2)";
  document.getElementById("head").scrollIntoView({block:"nearest",behavior:"smooth"});}
document.querySelectorAll("[data-path]").forEach(el=>{if(el.tagName!=="TR")el.addEventListener("click",()=>filter(el.dataset.path));});
</script></body></html>
"""


def sector(r0: float, r1: float, a0: float, a1: float) -> str:
    """SVG path of an annular sector; angles in radians, clockwise from 12 o'clock."""
    a1 = min(a1, a0 + 2 * math.pi - 1e-4)
    pad = min(0.006, (a1 - a0) / 4)
    a0, a1 = a0 + pad, a1 - pad
    big = 1 if a1 - a0 > math.pi else 0
    p = lambda r, a: f"{r * math.sin(a):.2f},{-r * math.cos(a):.2f}"   # noqa: E731
    return f"M{p(r1, a0)}A{r1},{r1} 0 {big} 1 {p(r1, a1)}L{p(r0, a1)}A{r0},{r0} 0 {big} 0 {p(r0, a0)}Z"


def ring(root: dict, size: str, colors: dict, centre: tuple[str, str]) -> str:
    """Arcs of a ring over `root` (nodes: name, kids, rules, leaves). Segment width ∝ node[size]; rule-less nodes grey."""
    depth = max_depth(root)
    radius = [R_IN + (R_OUT - R_IN) * i / depth for i in range(depth + 1)]
    out = []

    def draw(node, a0, a1, level, names, color):
        start, total = a0, sum(k[size] for k in node["kids"])
        for kid in node["kids"]:
            if not kid[size]:
                continue
            span = (a1 - a0) * kid[size] / total
            path = names + [kid["name"]]
            base = color or colors[kid["name"]]
            r0, r1 = radius[level], radius[level + 1] - 1
            label = " > ".join(path)
            fill = (f'fill="{base}" fill-opacity="{1 - 0.22 * level:.2f}"' if kid["rules"]
                    else 'style="fill:var(--empty)"')
            out.append(f'<path class="seg" d="{sector(r0, r1, start, start + span)}" {fill} '
                       f'data-path="{html.escape(label)}"><title>{html.escape(label)}: {kid["rules"]} rules'
                       f'</title></path>')
            mid, rm = start + span / 2, (r0 + r1) / 2
            room = int((span * rm - 8) / 6.2)              # characters that fit along the arc at 11px
            if room >= 4:                                  # labels follow the arc; upside-down ones are turned
                text = kid["name"] if len(kid["name"]) <= room else kid["name"][:room - 1] + "…"
                deg = math.degrees(mid)
                turn = deg + 180 if 90 < deg < 270 else deg
                ink = ("#fff" if level < 2 else "var(--fg)") if kid["rules"] else "var(--muted)"
                out.append(f'<text transform="translate({rm * math.sin(mid):.1f},{-rm * math.cos(mid):.1f}) '
                           f'rotate({turn:.1f})" text-anchor="middle" dy="0.35em" '
                           f'style="font-size:11px;fill:{ink}">{html.escape(text)}</text>')
            draw(kid, start, start + span, level + 1, path, base)
            start += span
    draw(root, 0.0, 2 * math.pi, 0, [], None)
    big, small = centre
    out.append('<circle r="62" fill="transparent" class="seg" data-path="" style="stroke:none"></circle>')
    out.append(f'<text text-anchor="middle" dy="-0.15em" style="font-size:24px;font-weight:600;fill:var(--fg)">'
               f'{big}</text><text text-anchor="middle" dy="1.4em" style="font-size:11px;fill:var(--muted)">'
               f'{small}</text>')
    return "\n".join(out)


def max_depth(node: dict) -> int:
    return 1 + max((max_depth(k) for k in node["kids"]), default=0) if node["kids"] else 0


def main():
    tree = load_tree(TREE)
    counts, rules, tasks = {}, [], []
    for path in sorted(paths.TASKS.glob("*-task-*/rules.json")):
        tid = paths.task_id(path.parent.name)
        tasks.append(tid)
        for r in json.loads(path.read_text()):
            if r.get("mapping"):
                rules.append((tid, r))
                p = tuple(r["mapping"]["path"])
                for i in range(1, len(p) + 1):
                    counts[p[:i]] = counts.get(p[:i], 0) + 1

    def full(node, prefix=()):                             # the whole tree, with rule and leaf counts
        kids = [full(k, prefix + (k.name,)) for k in node.children]
        return {"name": node.name, "path": prefix, "kids": kids, "rules": counts.get(prefix, 0) if prefix else len(rules),
                "leaves": sum(k["leaves"] for k in kids) if kids else 1}
    whole = full(tree)

    def reached(node):                                     # the same tree cut to the classes that hold a rule
        return {**node, "kids": [reached(k) for k in sorted(node["kids"], key=lambda k: -k["rules"]) if k["rules"]]}
    hit = reached(whole)

    colors = {k["name"]: (OTHER_COLOR if k["name"] == "Other" else PALETTE[i % len(PALETTE)])
              for i, k in enumerate(whole["kids"])}
    legend = [f'<span><span class="sw" style="background:{colors[k["name"]]}"></span>{html.escape(k["name"])} '
              f'{k["rules"]}</span>' for k in hit["kids"]]
    unreached = [k["name"] for k in whole["kids"] if not k["rules"]]
    if unreached:
        legend.append(f"<span>Not reached: {html.escape(', '.join(unreached))}</span>")

    def outline(node):
        items = []
        for k in node["kids"]:
            label = " > ".join(k["path"])
            count = f'<span class="c">{k["rules"]}</span>' if k["rules"] else ""
            sub = f"<ul>{outline(k)}</ul>" if k["kids"] else ""
            items.append(f'<li><span class="n{"" if k["rules"] else " z"}" data-path="{html.escape(label)}">'
                         f'{html.escape(k["name"])}</span>{count}{sub}</li>')
        return "".join(items)

    rows, low = [], 0
    for tid, r in sorted(rules, key=lambda x: (x[0], x[1]["item"])):
        m = r["mapping"]
        is_low = m["separation"] is not None and m["separation"] < 1.2
        low += is_low
        path = " > ".join(m["path"])
        rows.append(f'<tr data-path="{html.escape(path)}"{" data-low=1" if is_low else ""}>'
                    f'<td class="id">T{tid} · #{r["item"]}</td>'
                    f'<td title="{html.escape(r["constraint"])}">{html.escape(r.get("constraint_en") or r["constraint"])}'
                    f'<div class="cat">{html.escape(" / ".join(r["tags"]))} → '
                    f'{html.escape(path)}</div></td>'
                    f'<td class="num{" low" if is_low else ""}">{m["score"]:.2f} · sep {m["separation"]}</td></tr>')

    leaves = whole["leaves"]
    reached_leaves = sum(1 for p, n in counts.items() if n and not any(q[:len(p)] == p and len(q) > len(p)
                                                                         for q in counts))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(PAGE.replace("__RESULT__", ring(hit, "rules", colors, (str(len(rules)), "policy rules")))
                   .replace("__CLASSES__", ring(whole, "leaves", colors, (str(leaves), "leaf classes")))
                   .replace("__OUTLINE__", outline(whole)).replace("__ROWS__", "\n".join(rows))
                   .replace("__LEGEND__", "".join(legend)).replace("__N__", str(len(rules)))
                   .replace("__LOW__", str(low)).replace("__LEAVES__", str(leaves))
                   .replace("__REACHED__", str(reached_leaves)).replace("__TASKS__", ", ".join(map(str, tasks))))
    print(f"→ {OUT}  ({len(rules)} rules, {reached_leaves} of {leaves} leaf classes reached)")


if __name__ == "__main__":
    main()
