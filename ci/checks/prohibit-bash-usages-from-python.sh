#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -n -e bash --and --not -e compl -- '*.py' ':!git_machete/generated_docs.py' 'tests/' ':!tests/completion_e2e/'; then
  echo
  echo 'Do not rely on bash being installed, not even in tests.'
  echo 'See e.g. https://github.com/VirtusLab/git-machete/pull/929.'
  exit 1
fi
