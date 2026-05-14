#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -n -e bash --and --not -e compl -- '*.py' ':!git_machete/generated_docs.py' ':!git_machete/cli_commands.py' 'tests/' ':!tests/completion_e2e/' ':!tests/test_cli.py'; then
  echo
  echo 'Do not rely on bash being installed, not even in tests.'
  echo 'See e.g. https://github.com/VirtusLab/git-machete/pull/929.'
  exit 1
fi
