# Commands › flock
enforcer · A file lock (util-linux, in the image): `flock /tmp/<name>.lock <command>` runs a command alone, for checks that must
not run at the same time.

- check: `flock <lock file> <command>`: the command runs alone (checks that must not run at the same time)
