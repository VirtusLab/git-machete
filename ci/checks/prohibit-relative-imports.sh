#!/usr/bin/env bash

set -e -o pipefail -u

# Match `from .x import y` / `from ..x import y` style relative imports,
# whether at top level or indented inside a function/method.
# `\bfrom\s+\.` keeps the regex tight enough to avoid false positives on
# unrelated occurrences of the literal string "from ." inside string literals,
# since those are practically never preceded by "from " followed by whitespace
# at the start of a logical import statement.
if git grep -n -P '^\s*from\s+\.+\w*\s+import\b' -- '*.py'; then
  echo
  echo 'Do not use relative imports (`from .x import y`, `from ..x import y`, ...) in Python code.'
  echo 'Use the fully-qualified absolute form instead: `from git_machete.<...> import ...` or `from tests.<...> import ...`.'
  echo 'Absolute imports are easier to follow when reading code in isolation (no need to know the file'"'"'s package)'
  echo 'and survive moving a file across packages without a silent semantic change.'
  exit 1
fi
