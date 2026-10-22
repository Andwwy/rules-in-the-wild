"""Build the mapping ring of the trigger or target tree: where the voted values landed, and the whole tree.

    python ring.py trigger        → trigger ring.html (open it in a browser)
    python ring.py target         → target ring.html

Reads ../mapped/<axis>.jsonl (written by ../classifier/map_values.py) and the tree ../<axis>-tree.json. The page is
the one of `MTAC enforcement eval/experiment/scripts/ring.py`, for one axis of the v1.11 vote:

    Mapping result     ring sized by values: only the classes that values reached
    Decision classes   ring sized by leaves: every class of the tree; reached classes in colour, the rest grey;
                       plus the tree as an outline with each class's count

Each top-level class keeps one colour in both rings. A short script only filters the table when a segment or an outline
entry is clicked.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "classifier"))
from tree_classifier import AXES, load_tree                # noqa: E402

PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948", "#1f9ec4",
           "#a35a00", "#b23a8a", "#5b7c2a"]
OTHER_COLOR = "#8a8f8c"
R_IN, R_OUT = 64, 195

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
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
.scroll{max-height:640px;overflow:auto}
table{width:100%;border-collapse:collapse;font-size:13px}
td{border-top:1px solid var(--line);padding:7px 6px;vertical-align:top;overflow-wrap:anywhere}
.num{color:var(--muted);font-size:12px;font-variant-numeric:tabular-nums;white-space:nowrap;text-align:right}
.val{font-weight:600}
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
<h1>__TITLE__</h1>
<p class="sub">__N__ of the __TOTAL__ voted __AXIS__ values of the 1,841 rules that have a voted enforcer, target and trigger
(<code>v1.11.vote</code>), mapped by Jev onto <code>__TREE__</code>. Jev saw the rule text and the assigner's wording.
Click a segment or a class to list only its values; click a ring's centre to list all.</p>
__PILOT__
<h2>Mapping result</h2>
<p class="sub">Sized by values: only the classes that values reached.__ATTRS__</p>
<div class="legend">__LEGEND__</div>
<div class="wrap">
<svg viewBox="-200 -200 400 400" width="100%" role="img" aria-label="Ring of the values by tree path">
__RESULT__
</svg>
<div><p class="head" id="head">All mapped values</p><p class="meta" id="meta">__N__ values · __LOW__ close calls (separation under 1.2)</p>
<div class="scroll"><table><tbody id="rows">
__ROWS__
</tbody></table></div></div>
</div>

<h2>Decision classes</h2>
<p class="sub">The whole tree, sized by its __LEAVES__ leaf classes. Classes that values reached are in colour; the others are
grey. __REACHED__ of __LEAVES__ leaf classes hold a value. Hover a class for its description.</p>
<div class="wrap">
<svg viewBox="-200 -200 400 400" width="100%" role="img" aria-label="Ring of every class in the tree">
__CLASSES__
</svg>
<ul class="tree">__OUTLINE__</ul>
</div>
</div>
<script>
const rows=[...document.querySelectorAll("#rows tr")];
function filter(p){let n=0,low=0;
  rows.forEach(r=>{const on=!p||r.dataset.path===p||r.dataset.path.startsWith(p+" > ");r.hidden=!on;if(on){n++;if(r.dataset.low)low++;}});
  document.getElementById("head").textContent=p||"All mapped values";
  document.getElementById("meta").textContent=n+" values · "+low+" close calls (separation under 1.2)";
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


def max_depth(node: dict) -> int:
    return 1 + max((max_depth(k) for k in node["kids"]), default=0) if node["kids"] else 0


def ring(root: dict, size: str, colors: dict, centre: tuple[str, str], unit: str) -> str:
    """Arcs of a ring over `root` (nodes: name, kids, count, leaves). Segment width ∝ node[size]; empty nodes grey."""
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
            fill = (f'fill="{base}" fill-opacity="{1 - 0.22 * level:.2f}"' if kid["count"]
                    else 'style="fill:var(--empty)"')
            tip = f'{label}: {kid["count"]} {unit}' + (f' — {kid["description"]}' if kid["description"] else "")
            out.append(f'<path class="seg" d="{sector(r0, r1, start, start + span)}" {fill} '
                       f'data-path="{html.escape(label)}"><title>{html.escape(tip)}</title></path>')
            mid, rm = start + span / 2, (r0 + r1) / 2
            room = int((span * rm - 8) / 6.2)              # characters that fit along the arc at 11px
            if room >= 4:                                  # labels follow the arc; upside-down ones are turned
                text = kid["name"] if len(kid["name"]) <= room else kid["name"][:room - 1] + "…"
                deg = math.degrees(mid)
                turn = deg + 180 if 90 < deg < 270 else deg
                ink = ("#fff" if level < 2 else "var(--fg)") if kid["count"] else "var(--muted)"
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


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("axis", choices=["trigger", "target"])
    args = p.parse_args()
    axis = args.axis
    sys.path.insert(0, str(HERE.parent / "classifier"))
    from map_values import jobs                            # the scope's full value count, for the header
    total = len(jobs(axis, "full"))
    tree_file = AXES[axis].tree
    tree = load_tree(tree_file)
    mapped = [json.loads(line) for line in (HERE.parent / "mapped" / f"{axis}.jsonl").read_text().splitlines()]
    counts = {}
    for row in mapped:
        path = tuple(row["mapping"]["path"])
        for i in range(1, len(path) + 1):
            counts[path[:i]] = counts.get(path[:i], 0) + 1

    def full(node, prefix=()):                             # the whole tree, with value and leaf counts
        kids = [full(k, prefix + (k.name,)) for k in node.children]
        return {"name": node.name, "path": prefix, "kids": kids, "description": node.description,
                "count": counts.get(prefix, 0) if prefix else len(mapped),
                "leaves": sum(k["leaves"] for k in kids) if kids else 1}
    whole = full(tree)

    def reached(node):                                     # the same tree cut to the classes that hold a value
        return {**node, "kids": [reached(k) for k in sorted(node["kids"], key=lambda k: -k["count"]) if k["count"]]}
    hit = reached(whole)

    colors = {k["name"]: (OTHER_COLOR if k["name"] == "Other" else PALETTE[i % len(PALETTE)])
              for i, k in enumerate(whole["kids"])}
    legend = [f'<span><span class="sw" style="background:{colors[k["name"]]}"></span>{html.escape(k["name"])} '
              f'{k["count"]}</span>' for k in hit["kids"]]
    unreached = [k["name"] for k in whole["kids"] if not k["count"]]
    if unreached:
        legend.append(f"<span>Not reached: {html.escape(', '.join(unreached))}</span>")

    def outline(node):
        items = []
        for k in node["kids"]:
            label = " > ".join(k["path"])
            count = f'<span class="c">{k["count"]}</span>' if k["count"] else ""
            sub = f"<ul>{outline(k)}</ul>" if k["kids"] else ""
            tip = f' title="{html.escape(k["description"])}"' if k["description"] else ""
            items.append(f'<li><span class="n{"" if k["count"] else " z"}" data-path="{html.escape(label)}"{tip}>'
                         f'{html.escape(k["name"])}</span>{count}{sub}</li>')
        return "".join(items)

    rows, low = [], 0
    for row in sorted(mapped, key=lambda r: (r["mapping"]["path"], -r["mapping"]["score"])):
        m = row["mapping"]
        is_low = m["separation"] is not None and m["separation"] < 1.2
        low += is_low
        path = " > ".join(m["path"])
        attrs = m.get("attributes")
        extra = (f' · {attrs["timing"]}' + (" · needs a state" if attrs["state_p"] >= 0.5 else "")) if attrs else ""
        rows.append(f'<tr data-path="{html.escape(path)}"{" data-low=1" if is_low else ""}>'
                    f'<td><span class="val">{html.escape(row["value"])}</span>'
                    f'<div class="cat">{html.escape(path)}{html.escape(extra)}</div>'
                    f'<div class="cat">{html.escape(row["rule_text"][:300])}</div></td>'
                    f'<td class="num{" low" if is_low else ""}">{m["score"]:.2f} · sep {m["separation"]}</td></tr>')

    attrs_line = ""
    if axis == "trigger":
        timing, state = {}, 0
        for row in mapped:
            a = row["mapping"].get("attributes") or {}
            timing[a.get("timing")] = timing.get(a.get("timing"), 0) + 1
            state += a.get("state_p", 0) >= 0.5
        attrs_line = (" Timing (Jev): " + " · ".join(f"{k} {timing.get(k, 0)}" for k in ("before", "at", "after", "none"))
                      + f". Needs a state as well (p ≥ 0.5): {state}.")
    pilot = (f'<p class="sub low"><b>Pilot.</b> Only {len(mapped)} of {total} values are mapped so far. The tree ring below '
             f'is complete; the result ring fills in after the full run.</p>' if len(mapped) < total else "")

    leaves = whole["leaves"]
    reached_leaves = sum(1 for p_, n in counts.items() if n and not any(q[:len(p_)] == p_ and len(q) > len(p_)
                                                                          for q in counts))
    title = f"{axis.capitalize()} Mapping Ring"
    out = HERE / f"{axis} ring.html"
    out.write_text(PAGE.replace("__RESULT__", ring(hit, "count", colors, (str(len(mapped)), f"{axis} values"), "values"))
                   .replace("__CLASSES__", ring(whole, "leaves", colors, (str(leaves), "leaf classes"), "values"))
                   .replace("__OUTLINE__", outline(whole)).replace("__ROWS__", "\n".join(rows))
                   .replace("__LEGEND__", "".join(legend)).replace("__N__", f"{len(mapped):,}")
                   .replace("__TOTAL__", f"{total:,}").replace("__AXIS__", axis).replace("__TREE__", tree_file.name)
                   .replace("__PILOT__", pilot).replace("__ATTRS__", attrs_line).replace("__TITLE__", title)
                   .replace("__LOW__", str(low)).replace("__LEAVES__", str(leaves))
                   .replace("__REACHED__", str(reached_leaves)))
    print(f"→ {out}  ({len(mapped)} values, {reached_leaves} of {leaves} leaf classes reached)")


if __name__ == "__main__":
    main()
