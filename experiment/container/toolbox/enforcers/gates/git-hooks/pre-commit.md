# Gates › Git hooks › pre-commit
enforcer · A framework that runs the checks in a `.pre-commit-config.yaml` file when a commit is made.

- install: `pre-commit` (with `git`)
- check: a `.pre-commit-config.yaml` (local hooks: `repo: local`, `entry: <check>`) and `pre-commit install`; or `pre-commit run --files <file>`
- skeleton: /opt/enforce-toolbox/skeletons/pre_commit_check.sh (pre-commit runs a check on one file, outside a commit)

Docs: https://pre-commit.com/
