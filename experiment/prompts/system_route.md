
## The route of each rule

The rules come in one message. Each rule comes in this form:

    Rule R<n>: <the rule>

    - Enforcer: <leaf> (<its path in the tree>)
    - Trigger: <leaf> (<its path>), timing: <before | at | after | always>
    - Target: <leaf> (<its path>)

    <a card for each leaf, the first time the leaf comes: its node in the toolbox: what it means, and how to build it here>

The enforcer, the trigger and the target are the rule's route: three decisions that a classifier (Jev) made for the
rule. Each is a leaf of a tree of enforcement choices:

- Enforcer: the kind of check that enforces the rule, for example a regular-expression validator, a code scan or a
  check of the project's files.
- Trigger: the moment in the agent's work when the check runs, for example when the agent writes a file or sends a
  reply, with a timing: before, at or after that moment.
- Target: what the check reads, for example the agent's reply, a source file, or the functions in a file.

Implement each rule with its route.
