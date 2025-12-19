#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -E -i -n -e 'grey' -- :!ci/checks/ :!RELEASE_NOTES.md; then
  echo
  echo 'Stray usage of `grey` found. Use `gray` instead.'
  exit 1
fi
