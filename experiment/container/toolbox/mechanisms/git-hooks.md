# Git hooks
mechanism · before a commit, a push, a merge (install: `git`)

For every repository: `git config --system core.hooksPath /opt/enforce/git-hooks`, a root-owned folder with one
executable script per hook (`pre-commit`, `commit-msg`, `pre-push`, …; /opt/docs/git/githooks.adoc). Exit 1 stops
the git action.

- skeleton: /opt/enforce-toolbox/skeletons/pre-commit.sh
- the agent sees: git's error, with the hook's output.
- limits: the agent can skip it (`git commit --no-verify`, `git -c core.hooksPath=…`); /workspace has no repository at the start.

- docs: https://git-scm.com/docs/githooks
- runs as the agent: state that the agent must not change (a history, a count) belongs to a root service: /opt/enforce-toolbox/mechanisms/root-service.md
