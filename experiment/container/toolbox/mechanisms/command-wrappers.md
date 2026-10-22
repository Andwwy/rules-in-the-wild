# Command wrappers
mechanism · before a command runs

A root-owned script with the program's name, in a folder that comes earlier on the agent's PATH than the program (see
the agent's PATH: `runuser -u agent -- bash -lc 'echo $PATH'`), checks the command line, then runs the program.

- skeleton: /opt/enforce-toolbox/skeletons/wrapper.sh
- the agent sees: the wrapper's message and its exit code.
- limits: the agent can still run the program by its full path.
- runs as the agent: state that the agent must not change (a history, a count) belongs to a root service: /opt/enforce-toolbox/mechanisms/root-service.md
