# Gates › CI / hosting › Branch protection
enforcer · Code-host settings that refuse a merge into a branch until the checks pass or reviewers approve.

- not here: no code host
- nearest: a check that refuses `git commit` or `git push` on a protected branch (Command filter (/opt/enforce-toolbox/enforcers/gates/tools/command-filter.md), or a git hook (/opt/enforce-toolbox/mechanisms/git-hooks.md))
