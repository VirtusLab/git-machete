#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -EIn 'MR|-mr|[mM]erge [rR]equest' -- '*github*' :!ci/checks/; then
  echo
  echo "GitHub uses *pull* requests rather than *merge* requests, please fix"
  exit 1
fi
