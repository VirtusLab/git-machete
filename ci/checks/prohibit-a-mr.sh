#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -EIn 'a MR' -- :!ci/checks/; then
  echo
  echo "Use *an* MR ('em are'), not *a* MR"
  exit 1
fi
