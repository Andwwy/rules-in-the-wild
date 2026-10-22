# Validation › Regex › Other
enforcer · A pattern check of another kind (for example glob patterns on file names).

- check: a regular expression in a check script (/opt/enforce-toolbox/skeletons/check.py), or `grep -n -E '<pattern>' <file>` (exit 0 when it matches: invert for "must not")
