# File watchers
mechanism · after a file changes (install: `inotify-tools`)

A root process that keeps running reports each change in a folder as it happens (`inotifywait -m -r`), and runs a
check on the changed file.

- skeleton: /opt/enforce-toolbox/skeletons/watcher.sh
- the agent sees: nothing directly: the watcher cannot refuse the change; it can undo it (from a copy), or leave a note.
- keep its log and copies in /var/lib/enforce-state.
- trials: while /run/enforce/trial exists, `try` is changing /workspace (it also restores it afterwards): skip those changes.

- docs: https://github.com/inotify-tools/inotify-tools/wiki
