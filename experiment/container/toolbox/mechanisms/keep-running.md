# Checks that keep running
mechanism · after the fact, from time to time

A root process that runs a check on the whole project again and again: `nohup bash -c 'while sleep <seconds>; do
<check> || <act>; done' > /opt/enforce/<name>.log 2>&1 &`. For rules on the project's state.

- runs: /opt/enforce-toolbox/skeletons/project_check.py, or any check
- the agent sees: nothing directly (as file watchers): it can undo, or leave a note.
- keep its state in /var/lib/enforce-state.
