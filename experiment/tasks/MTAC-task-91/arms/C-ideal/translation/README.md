# C-ideal: C's routes, translated by hand (task 91)

The ideal translation of arm C: each rule enforced with its route from `rules.json` (enforcer, trigger with its timing,
target), using only C's share of the toolbox (`toolbox.json`, the same as C's). It was written by Claude Opus 5.5 in
the local session, from the rules' text, the routes and the cards, not from MTAC's checker code. It replaces the
translation agent: `runner.py 91 C-ideal` copies `enforce/` to /opt/enforce and runs `install.sh` as root, then the
task turns run as in every arm (design_process.md, point 107). B's run (20261018T171513Z) stays the naive translation.

| rule | route: enforcer · trigger, timing · target | how |
|---|---|---|
| R1 喵～ first | Regex validator · Response sent, before · reply | `R1_reply_start.py`, at Stop |
| R2 代码小灵, not 我 | Regex filter · Response sent, before · reply | `R2_self_reference.py`, at Stop: 我 → 代码小灵; the fixed lines go back to the agent |
| R3 开发者大大, not 你 | Regex validator · Response sent, before · reply | `R3_address_user.py`, at Stop |
| R4 Chinese | Regex validator · Always · reply | `R4_chinese.py`, at Stop (every reply) |
| R5 coding line 1 | pre-commit · File write / edit, before · source file | `R5_pre_commit.sh` runs `R5_coding_line.py` by pre-commit; before Write, Edit, MultiEdit (on the new content) |
| R6 AI-Assisted line | Regex validator · File write / edit, after · source file | `R6_ai_note.py`, at Stop, on every code file (the card's "after": end of the turn, every file) |
| R7 functions ≤ 60 lines | Semgrep · File write / edit, before · function | `R7_function_length.py`: Semgrep finds every function and method, the script counts its lines; before Write, Edit, MultiEdit |
| R8 哒～ last | Regex validator · Response sent, at · reply | `R8_reply_end.py`, at Stop |

Hooks (`enforce/settings.json`, installed as /workspace/.claude/settings.json, root's and immutable, in a folder
that is root's): `hooks/before_write.py` (PreToolUse), `hooks/after_bash.py` (PostToolUse on Bash),
`hooks/end_of_turn.py` (Stop); `hooks/on_disk.py` is R5 and R7 on the files on disk. Where the route cannot be
followed exactly:

- **R2's filter.** A Stop hook cannot rewrite the reply, so the filter refuses it and gives the fixed lines back (the
  regex filter card's other way).
- **Before and at a reply** are the same moment in Claude Code: Stop, before the reply is final.
- **R5 and R7 for shell writes.** A shell command's writes cannot be seen before it runs. After each Bash call, R5 and
  R7 check every code file on disk (the earliest moment possible), and again at Stop, so that the turn cannot end with
  a file from the shell that breaks them (a block after a command is feedback the agent can pass over).
- **R7 in shell scripts.** Semgrep 1.177 has no Bash pattern for a function definition, so R7 finds shell functions by
  their braces.

## What each check reads (point 108)

From the rules' text; `enforce/tests/semantics.py` holds the cases, and install.sh runs them in every run's container
as the agent (a failed case stops the install).

- **The reply** is the turn's last non-empty assistant text, what the user gets. **The agent's own prose** in it is the
  reply without code (fenced, inline), markup tags, links, paths and file names, and quoted text (another's words, a
  UI text, a term): `common.prose`.
- **R1, R8**: the reply's first characters are 喵～, its last are 哒～ (as written: 喵~ and 哒~ are not them).
- **R2**: in the prose, the pronoun 我 (also 我的) for the agent. Not 我们 ("we": 代码小灵 cannot replace it), nor words
  where 我 is not the agent (自我, 忘我, 本我, 敌我, 我方, 我国).
- **R3**: in the prose, the second person 你, 您, 妳 (also 你们, 你的). Not 迷你 ("mini").
- **R4**: the prose has Chinese, no English sentence (six or more English words in a row) and no common English word
  (Done, passed, the, please, …). Technical terms, names and keywords used as terms (HTML5, CSS Grid, Playwright,
  "用 for 循环") pass, as in Chinese technical writing; so do the XML tags that turn 5 asks for.
- **R5**: line 1 is a comment in the file's own syntax (HTML `<!-- -->`, CSS `/* */`, JS `//` or `/* */`, Python and
  shell `#`) with `-*- coding: utf-8 -*-` as written. A `#` line in HTML is text before the doctype, and in JavaScript
  a syntax error: it does not declare the encoding.
- **R6**: one of lines 1 to 3 is a comment of its own (not the coding line), in the file's own syntax, with the
  sentence as given (its final period too). A docstring is not a comment.
- **R7**: every function, method, arrow function and callback, nested or not, from its signature's line to its last
  line: at most 60. Also in HTML, Vue and Svelte `<script>` blocks, Python and shell. Top-level code is not a function.
- **Code files**: by name, as GitHub Linguist's kinds: programming and markup languages count; documents and data
  (Markdown, text, JSON, YAML) and binary files do not. A file whose name says neither is code only when its content
  says so (a `#!` line); an output file such as `0` is not. Under /workspace, node_modules, .git, caches and .claude are
  skipped.

## How it was checked (point 108)

- `tests/semantics.py`: 77 check cases and 11 hook cases, all as expected, in the run image.
- **Against MTAC's verdicts** (outcomes only; its checker code stays unread), on every scored task 91 run (90 turns:
  each reply and workspace): R1, R2, R3, R6, R7, R8 agree in all 90 turns. R5 agrees except in 31 turns, all files whose
  line 1 is `# -*- coding: utf-8 -*-` in HTML or JavaScript, which MTAC passes and this check does not (above).
- **In Claude Code 2.1.199**, a scripted task turn (`chain_scenario.json`, `runner.py 91 C-ideal --mock ... --turns 1`,
  no model call; checks/MTAC-task-91/C-ideal/20261022T045506Z): a Write without the coding line refused (R5); a
  62-line function refused (R7); a file from the shell blocked after the command (R5) and again at the end of the turn
  (R5, R6); an English reply sent back (R1, R4, R8); a reply with 我 and 你 sent back with the filtered line (R2, R3);
  the conforming reply passed.
- The run of point 107 (80/80) used the version before these changes: R2, R3 and R4 read the whole reply; files from
  the shell were not checked again at the end of the turn; shell functions and output files without a kind were not
  handled as above.

## The run (2026-10-22)

`agents/haiku-4.5_claude-code-2.1.199/runs/MTAC-task-91/C-ideal/20261022T042020Z`: phase 0 by hand (25 s, no model),
then the 10 task turns (Haiku 4.5, $1.86 in the ledger). MTAC's checker scripts: **80/80** (policy items 70/70), against
A 62/80 (policy 55/70) and B, the naive translation, 65/80 (policy 55/70). R1 10/10 (A and B 0/10), R5 10/10, R6
10/10, R7 10/10 (A 6/10, B 7/10). The hooks acted 5 times: turn 1 refused index.html with a `#` coding line and sent
back a reply without 喵～; turn 10 refused test_game.py twice (a shebang on line 1; a 67-line test function) and sent
the turn back once for its missing AI-Assisted line. In turns 2 to 9 no hook had to act.

Held-out cases (`score_phase0.py`, read only after the enforcement was written, not used to change it): R1, R2, R3, R5,
R6, R7, R8 caught in every case, by file tool and by shell; R4 missed "an English word in the reply" (R4 here flags
English sentences); one false flag: R2 here flags 我们, the cases count it out of R2's scope. After point 108 (the
version above): every case caught, no false flag (checks/MTAC-task-91/C-ideal/20261022T045506Z). The R2 and R4 changes
were made from the rules' text, but after these two case names had been seen: for R2 and R4 this score is not
independent.

Not results: `20261022T041454Z` (phase 0 only, free) and `20261022T041817Z` (stopped after turn 1, $0.19: the first R5
took a `#` line in HTML; fixed so R5 and R6 need the file's own comment syntax).

The translation's own cost: Claude Opus 5.5 in the local Claude Code session, from the goal to the start of the run:
50 model calls, 86,429 output tokens, 218,810 cache-write tokens (1-hour), 9,611,753 cache-read tokens, 100 uncached
input tokens. At the Claude API's prices for Opus 5.5 ($4 input, $20 output, $8 1-hour cache write, $0.20 cache read
per million tokens) that is about **$5.40** (output $1.73, cache writes $1.75, cache reads $1.92). Watching the run and
scoring it took 15 more calls, about $1.61 (to the time of writing). Counted from the session's own transcript (each
reply's `usage`).

Point 108 (checking what each check reads, and that it works): 26 more calls, 55,728 output tokens, 76,150 cache-write
tokens, 10,002,685 cache-read tokens: about $3.72 at the same prices.

## The run of the checked version (2026-10-22, point 109)

`runs/MTAC-task-91/C-ideal/20261022T074435Z` (Haiku 4.5, $1.15): policy items **70/70** again (only the policy rules are
scored now, point 110; before that it counted 77/80 items with the turns' own requests). The three failed requests are turn 7, 8 and 9's own indentation request (4, 2, 4 spaces): one continuation line in
index.html aligned under a parenthesis (19, 13, 19 spaces); no hook acted after turn 1, so the enforcement did not
cause it (A failed the same three turns). The hooks acted twice, both in turn 1: index.html with a `#` coding line
(R5, refused) and a reply without 喵～ (R1).
