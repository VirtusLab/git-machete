#!/usr/bin/env bash

set -e -o pipefail -u

# Match whole words that end with a single trailing underscore (e.g. branch_, hash_).
# -w ensures visit_FunctionDef and _member_names_ do not match (same word continues after _).
# Such names are error-prone ().
matches=$(git grep -n -E -w '[a-z][a-z0-9]*_' -- '*.py' ':!tests/' ':!flake8/' | grep -v 'CODE_HOSTING_TOKEN_PREFIXES' || true)
if [[ -n $matches ]]; then
  echo "$matches"
  echo
  echo 'Do not use trailing underscore in variable/parameter names (e.g. branch_, foo_),'
  echo 'as they are easy to confuse with the non-underscore name from outer scope.'
  echo 'Use descriptive names instead (e.g. for_branch, current_branch where appropriate).'
  exit 1
fi
