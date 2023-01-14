#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -n "^[^']*'[^s][^']*\\\\$" || git grep -n '^[^"]*"[^"]*\\$'; then
  echo 'The above lines apparently contains a backslash continuation within the string.'
  echo 'This might lead to unwanted whitespace making its way into strings, see https://github.com/VirtusLab/git-machete/issues/784'
  echo "Change into  '...' \\  or  \"...\" \\  style of continuation (the string must be closed within the containing line)."
  exit 1
fi
