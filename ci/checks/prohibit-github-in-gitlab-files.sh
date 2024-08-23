#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -E -i -n -e 'github' --and --not -e 'report this error|valid GitLab project' -- '*gitlab*' ':!**/prohibit-*-in-*-files.sh'; then
  echo
  echo 'Stray usage of `github` in GitLab-related file(s), is it a copy-paste error?'
  exit 1
fi
