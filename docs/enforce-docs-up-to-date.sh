#!/usr/bin/env bash

set -e -o pipefail -u

current_docs=$(cat git_machete/docs.py)
generated_docs=$(python docs/generate_py_docs.py)

if [[ "$current_docs" != "$generated_docs" ]]; then
  echo "Command line docs are not up-to-date. Please regenerate docs via tox -e py_docs"
  exit 1
fi
