#!/bin/bash
# The library's tests (test_library.py) in MTAC's image, as root, with the library read-only at /opt/enforce-toolbox
# as scripts/runner.py copies it. Free: no model calls; it downloads the recipes' tools (about 1.1 GB).
#   container/toolbox/tests/in_image.sh
set -euo pipefail
library="$(cd "$(dirname "$0")/.." && pwd)"
docker run --rm --platform linux/amd64 -v "$library:/opt/enforce-toolbox:ro" -e PYTHONDONTWRITEBYTECODE=1 \
  alexgshaw/break-filter-js-from-html:20251031 python3 /opt/enforce-toolbox/tests/test_library.py
