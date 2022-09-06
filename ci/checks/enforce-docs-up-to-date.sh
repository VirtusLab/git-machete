#!/usr/bin/env bash

set -e -o pipefail -u

pip install bs4
pip install docutils
pip install pygments

current_docs=$(cat git_machete/docs.py)
echo "$current_docs"
generated_docs=$(python docs/generate_docs.py dont_save)
echo "$generated_docs"

diff <(echo "$current_docs") <(echo "$generated_docs")
if [[ "$current_docs" != "$generated_docs" ]]; then
  echo "Command line docs are not up-to-date. Please regenerate docs via tox -e docs"
  exit 1
fi
