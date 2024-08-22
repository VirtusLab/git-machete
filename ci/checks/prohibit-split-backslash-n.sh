#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -n 'split(.\\n.)' -- '*.py'; then
  # shellcheck disable=SC2028
  echo 'Do not use split("\\n") on strings as it does not cover \\r\\n line breaks; use splitlines() instead'
  exit 1
fi
