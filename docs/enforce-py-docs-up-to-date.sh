#!/usr/bin/env bash

set -e -o pipefail -u

current_docs=$(<git_machete/generated_docs.py)
generated_docs=$(python docs/generate_py_docs.py)

if [[ "$current_docs" != "$generated_docs" ]]; then
  echo "Command line docs are not up-to-date with the sources. Please regenerate docs via 'tox -e py-docs'."
  exit 1
fi
