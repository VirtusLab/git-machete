#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -n -F -e '…' -- :!ci/checks/ :!RELEASE_NOTES.md; then
  echo
  echo 'Stray usage of the `…` (U+2026) character found. Use plain `...` (three dots) instead.'
  exit 1
fi
