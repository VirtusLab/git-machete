#!/usr/bin/env bash

set -e -o pipefail -u

file=git_machete/git.py
# Guard against the file being renamed/moved without this script being updated:
# without this check, `git grep` below would fail with "ambiguous argument",
# but its non-zero exit would be swallowed by the surrounding `if` and the
# script would silently pass, defeating the whole purpose of the check.
if ! [[ -f $file ]]; then
  echo "$file does not exist under the expected path; update this script after the rename/move"
  exit 1
fi

if git grep -n 'fork.point' $file; then
  echo
  echo "The above lines in $file refer to 'fork point'."
  echo "$file should be oblivious to git-machete-specific concepts like fork point, please rename or move the code"
  exit 1
fi
