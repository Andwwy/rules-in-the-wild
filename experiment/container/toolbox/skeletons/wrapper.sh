#!/bin/bash
# /usr/local/bin/<program>: checks the arguments, then runs the real program
for arg in "$@"; do
  case "$arg" in
    <forbidden argument>) echo "<rule id>: <the rule>; <what to do instead>" >&2; exit 1 ;;
  esac
done
exec /usr/bin/<program> "$@"
