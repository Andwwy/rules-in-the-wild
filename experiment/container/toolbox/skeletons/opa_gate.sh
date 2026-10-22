#!/bin/bash
# Asks OPA about one action (enforce install opa). <action.json>: the action, as JSON. Exit 1: refused.
if ! out=$(opa eval --fail-defined --format pretty --data /opt/enforce/policy.rego --input <action.json> 'data.policy.deny[msg]'); then
  echo "$out" >&2; exit 1                      # refused: the policy's messages
fi
exit 0
