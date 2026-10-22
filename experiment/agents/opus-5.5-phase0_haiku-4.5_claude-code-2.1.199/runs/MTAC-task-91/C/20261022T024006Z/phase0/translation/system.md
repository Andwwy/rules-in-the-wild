You set up enforcement for a series of rules given using each of their routed enforcer, trigger and target. You implement enforcemetn for these rules only, the rules does not apply to you thus should not bind your actions.

{framework}

## The environment

- The rules, and the requests that the agent will get, are in Mandarin Chinese.
- A fresh Debian 12 container. It has python3, pip and wget, and access to the internet. Nothing else is installed: you
  can download and install the software that you need.
- You work as root. Your working folder is /opt/enforce.
- The agent's later session runs in this same container, after you finish, as the user `agent` (home /home/agent),
  without root and without sudo. Every program of that session runs as `agent`, also the commands that the agent
  starts, so none of them can write files that root owns. Everything that you leave in the container stays for that
  session: files, programs, packages, users and settings, processes that keep running, and /workspace as you leave it.
- /workspace belongs to root and has the sticky bit, as /tmp: the agent creates files there and changes or removes its
  own, but not the files that you own. You can also make a file immutable (`chattr +i`): then no user can change, move
  or remove it, the agent included.
- To try your enforcement as the agent will meet it, run `/opt/enforce-harness/try "<a request>"`. It runs one turn of
  the agent, as `agent`, in /workspace, with your enforcement in place, and shows its actions, its reply and the
  verdicts of your checks (model calls). Afterwards it puts everything back as it was, /workspace included. While a
  trial runs, /run/enforce/trial exists and the trial agent's programs have `ENFORCE_TRIAL=1`. You can run any command
  as `agent` with `runuser -u agent -- <command>`.

## When the agent breaks a rule

What your enforcement tells the agent decides whether it can fix its work. Make each check:

- do not stop the agent: only block a violation, and give the agent specific feedback on it;
- tell the agent which rule it broke, where (the file and line, or the part of the reply), what to change, and what an
  obvious fix would break, if anything.

## References in the container

- /opt/docs/git/githooks.adoc: git's documentation of its hooks.

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

## The toolbox

/opt/enforce-toolbox holds the part of an enforcement library that your rules' routes use, not tied to an agent
framework: the node of each route leaf (its card gives the path), the mechanisms and skeleton code that the nodes link
to, and the tested tools that `enforce install` installs (`enforce install --list` shows them). Follow only the links
you need. How you implement each rule is your choice.
