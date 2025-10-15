#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -E -i -n -e 'gitlab' --and --not -e 'valid GitHub repo' -- '*github*' :!ci/checks/; then
  echo
  echo 'Stray usage of `gitlab` in GitHub-related file(s), is it a copy-paste error?'
  exit 1
fi
