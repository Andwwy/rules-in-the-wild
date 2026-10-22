# Agent action › File read
trigger · A file is read, opened or loaded.

- before: the agent framework's hook (/opt/enforce-toolbox/mechanisms/framework-hooks.md) before its read tools; file permissions (/opt/enforce-toolbox/mechanisms/file-permissions.md) (`chmod 0600`: the agent cannot read)
- at: file watchers (/opt/enforce-toolbox/mechanisms/file-watchers.md) (`-e open,access`)
