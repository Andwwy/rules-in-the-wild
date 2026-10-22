# Build / ops › Operations › File permissions
enforcer · Unix file modes and owners: who may read, write or run a file.

- check: `find <folder> -perm -o+w` (files that every user can write), `stat -c '%U %a' <file>`; or set the permissions so the action cannot happen (/opt/enforce-toolbox/mechanisms/file-permissions.md)
