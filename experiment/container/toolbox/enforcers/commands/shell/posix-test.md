# Commands › Shell › POSIX test
enforcer · The `test` command (`[ … ]`): a file exists (`-e`), is a file (`-f`), is not empty (`-s`); compare strings and numbers.
For simple conditions in a shell check.

- check: `test -e <path>` (and `-f`, `-d`, `-s`, `-x`, …): exit 1 when the condition fails
