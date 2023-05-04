#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -n bash -- tests/ '*.py'; then
  echo
  echo 'Do not rely on bash being installed, not even in tests.'
  echo 'See e.g. https://github.com/VirtusLab/git-machete/pull/929.'
  exit 1
fi
