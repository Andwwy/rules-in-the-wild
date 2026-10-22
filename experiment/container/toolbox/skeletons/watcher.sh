#!/bin/bash
# A file watcher, started by root; it keeps running (enforce install inotify-tools).
nohup bash -c 'inotifywait -m -r -e close_write,moved_to --format "%w%f" /workspace |
  while read -r f; do [ -e /run/enforce/trial ] && continue
    <check> "$f" || <act: put the file back from a copy, or write a note>; done' \
  > /var/lib/enforce-state/watch.log 2>&1 &
