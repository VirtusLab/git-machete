#!/usr/bin/env bash

set -e -o pipefail -u

target_dir=$1

# `-t html` is needed for the conditionally rendered sections
sphinx-build -W --keep-going -b html -t html docs/source "$target_dir"

# To view the generated file(s), use
#   open     docs/html/index.html  # macOS
#   xdg-open docs/html/index.html  # Linux
