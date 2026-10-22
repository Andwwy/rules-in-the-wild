#!/bin/bash
# dogwood_gate.sh request|response '<event>': records one agent action in a trace and, for a request, asks Dogwood
# whether it is allowed now, given what happened before and when (enforce install dogwood). Call it before an action
# (request: exit 1 refuses it) and after it (response: records the outcome, which later decisions read).
#   request:  scope(principal: Agent::User::"agent", resource: Agent::Workspace::"workspace")
#             request_context(input: { command: "git push" })
#             Agent::Action::"Push"::request(input: { command: "git push" }, callerPrincipal: Agent::User::"agent",
#             callerResource: Agent::Workspace::"workspace", requestId: "<id>")
#   response: scope(…) Agent::Action::"RunTests"::response(input: { command: "pytest" }, output: { passed: true },
#             callerPrincipal: Agent::User::"agent", callerResource: Agent::Workspace::"workspace", requestId: "<id>")
# Only past events of the request's principal count: every event names it (callerPrincipal, callerResource).
# Run it as root, inside a root service (/opt/enforce-toolbox/mechanisms/root-service.md): the trace is the history
# that the agent must not change.
DIR=/opt/enforce/dogwood                      # policy.dw, schema.cedarschema (the definition)
TRACE=/var/lib/enforce-state/dogwood/trace.log  # the history (root only)
mkdir -p "$(dirname "$TRACE")"
echo "@$(date +%s) $2" >> "$TRACE"
[ "$1" = request ] || exit 0
verdict=$(dogwood replay "$DIR/policy.dw" --policy-schema "$DIR/schema.cedarschema" --trace "$TRACE" | tail -1)
case "$verdict" in
  *DENY*) echo "<rule id>: <the rule>; <what must happen first>" >&2; exit 1 ;;
esac
exit 0
