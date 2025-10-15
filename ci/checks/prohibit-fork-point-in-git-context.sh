#!/usr/bin/env bash

set -e -o pipefail -u

file=git_machete/git_operations.py
if git grep -n 'fork.point' $file; then
  echo
  echo "The above lines in $file refer to 'fork point'."
  echo "$file should be oblivious to git-machete-specific concepts like fork point, please rename or move the code"
  exit 1
fi
