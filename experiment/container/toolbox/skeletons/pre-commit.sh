#!/bin/bash
# /opt/enforce/git-hooks/pre-commit: checks the staged files
git diff --cached --name-only --diff-filter=ACM | while read -r f; do
  <check> "$f" || exit 1
done
