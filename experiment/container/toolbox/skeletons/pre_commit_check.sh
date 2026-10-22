#!/bin/bash
# <rule id>: <the rule>, run by pre-commit on one file, outside a commit.   pre_commit_check.sh FILE
# pre-commit needs a git repository: the file is copied into a throwaway one with this config, and
# `pre-commit run --files` runs its hooks (the local hook's entry is the check itself). Exit: pre-commit's own
# (1 when a hook fails, with its output). pre-commit is called by its full path: a hook runs with the agent's PATH.
PRE_COMMIT=/opt/enforce/tool-installs/bin/pre-commit
f="$1"; d=$(mktemp -d); trap 'rm -rf "$d"' EXIT
cp "$f" "$d/" && cd "$d" && git init -q && git config user.email check@local && git config user.name check
cat > .pre-commit-config.yaml <<'YAML'
repos:
- repo: local
  hooks:
  - id: <rule id>
    name: <rule id> <the rule>
    entry: <the check, run on each file it is given>
    language: system
YAML
git add -A >/dev/null 2>&1
PRE_COMMIT_HOME="$d/.cache" "$PRE_COMMIT" run --files "$(basename "$f")"
