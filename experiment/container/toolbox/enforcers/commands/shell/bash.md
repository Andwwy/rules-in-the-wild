# Commands › Shell › Bash
enforcer · A check written as a Bash script (`/bin/bash` is in the image). Use `set -euo pipefail`; for a violation, write the
message to stderr and exit with code 2.

- check: `bash -c '<script; the file is $1>' bash <file>`: a non-zero exit is a violation
