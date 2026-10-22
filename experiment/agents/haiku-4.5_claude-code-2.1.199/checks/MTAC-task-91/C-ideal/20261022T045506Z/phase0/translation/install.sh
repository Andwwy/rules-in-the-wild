#!/bin/bash
# The hand-made phase 0 of C-ideal, run as root after its files are in /opt/enforce (runner.py): the tools that the
# routes name (the toolbox's recipes), then the agent's Claude Code settings in the project scope of /workspace, which
# the agent cannot change (the folder and the file are root's; the file is immutable).
set -euo pipefail
enforce install git pre-commit semgrep
chown -R root:root /opt/enforce && chmod -R a+rX,go-w /opt/enforce
mkdir -p /workspace/.claude
install -o root -g root -m 0644 /opt/enforce/settings.json /workspace/.claude/settings.json
chown root:root /workspace/.claude && chmod 0755 /workspace/.claude
chattr +i /workspace/.claude/settings.json
# every check and hook, as the agent will run them, on what each rule must flag and must pass (tests/semantics.py)
runuser -u agent -- /usr/bin/python3 -I /opt/enforce/tests/semantics.py
echo "phase 0 (C-ideal): installed"
