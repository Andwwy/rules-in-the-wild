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
| R3 开发者大大, not 你 | Regex validator · Response sent, before · reply | `R3_address_user.py`, at Stop: 你 or 您 |
| R4 Chinese | Regex validator · Always · reply | `R4_chinese.py`, at Stop (every reply): Chinese, and no English sentence (6+ words) outside code |
| R5 coding line 1 | pre-commit · File write / edit, before · source file | `R5_pre_commit.sh` runs `R5_coding_line.py` by pre-commit; before Write, Edit, MultiEdit (on the new content) |
| R6 AI-Assisted line | Regex validator · File write / edit, after · source file | `R6_ai_note.py`, at Stop, on every code file (the card's "after": end of the turn, every file) |
| R7 functions ≤ 60 lines | Semgrep · File write / edit, before · function | `R7_function_length.py`: Semgrep finds every function and method, the script counts its lines; before Write, Edit, MultiEdit |
| R8 哒～ last | Regex validator · Response sent, at · reply | `R8_reply_end.py`, at Stop |

Hooks (`enforce/settings.json`, installed as /workspace/.claude/settings.json, root's and immutable, in a folder
that is root's): `hooks/before_write.py` (PreToolUse), `hooks/after_bash.py` (PostToolUse on Bash),
`hooks/end_of_turn.py` (Stop). Where the route cannot be followed exactly:

- **R2's filter.** A Stop hook cannot rewrite the reply, so the filter refuses it and gives the fixed lines back (the
  regex filter card's other way).
- **Before and at a reply** are the same moment in Claude Code: Stop, before the reply is final.
- **R5 and R7 for shell writes.** A shell command's writes cannot be seen before it runs. After each Bash call, R5 and
  R7 check every code file on disk. This is the earliest moment possible.

Which files are code: by name, as GitHub Linguist's kinds (`common.py`). Programming and markup files count; documents
and data do not; a text file of unknown kind is checked. Under /workspace, node_modules, .git, caches and .claude are
skipped. Choices made from the rules' text: R2 also flags 我 in 我们 and 我的; R3 also flags 您; R6 must be in lines 1
to 3, on a comment line of its own.
