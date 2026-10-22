#!/bin/bash
# R5 run by pre-commit on files, outside a commit (/opt/enforce-toolbox/skeletons/pre_commit_check.sh).
#   R5_pre_commit.sh ROOT REL ...   each ROOT/REL is copied into a throwaway git repository at REL, where
# `pre-commit run --files` runs the local hook R5 (its entry is the check, R5_coding_line.py). Exit: pre-commit's own
# (1 when the check fails, with its output: one line "R5 <REL>:1: ..." per file). Programs by their full paths: a hook
# runs with the agent's PATH.
PRE_COMMIT=/opt/enforce/tool-installs/bin/pre-commit
root="$1"; shift
d=$(mktemp -d); trap 'rm -rf "$d"' EXIT
for f in "$@"; do mkdir -p "$d/$(dirname "$f")" && cp "$root/$f" "$d/$f"; done
cd "$d" && /usr/bin/git init -q && /usr/bin/git config user.email check@local && /usr/bin/git config user.name check
cat > .pre-commit-config.yaml <<'YAML'
repos:
- repo: local
  hooks:
  - id: R5
    name: the utf-8 coding line, rule five
    entry: /usr/bin/python3 -I /opt/enforce/R5_coding_line.py
    language: system
YAML
/usr/bin/git add -A >/dev/null 2>&1
PRE_COMMIT_HOME="$d/.cache" "$PRE_COMMIT" run --color never --files "$@"
