#!/usr/bin/env bash

set -e -o pipefail -u

self_name=$(basename "$0")

if git grep -EIn 'MR|-mr|[mM]erge [rR]equest' -- '*github*' :!**/$self_name; then
  echo
  echo "GitHub uses *pull* requests rather than *merge* requests, please fix"
  exit 1
fi
