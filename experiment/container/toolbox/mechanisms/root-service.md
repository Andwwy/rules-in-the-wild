# Root service
mechanism · before an action, with state that only root keeps

The parts that run as the agent (framework hooks, command wrappers, git hooks) can keep nothing the agent cannot change:
whatever they write, the agent can write too. They ask a root process instead. The service keeps running from phase 0
on, keeps the history and the state in /var/lib/enforce-state, decides each request (a check, a policy:
/opt/enforce-toolbox/mechanisms/policy-opa.md, /opt/enforce-toolbox/mechanisms/policy-dogwood.md), and answers allow
or refuse with its message.

- skeletons: /opt/enforce-toolbox/skeletons/service.py (the service), /opt/enforce-toolbox/skeletons/ask_service.py (what an agent-side part runs)
- the agent sees: what the part that asked passes on.
- limits: when the service is down, the asking part must refuse or let pass (ask_service.py says where); the service cannot tell a hook from the agent's own shell by the socket alone, so it checks the request, not the caller.
- trials: requests made while /run/enforce/trial exists come from `try`.
