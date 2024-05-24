#!/usr/bin/env bash

set -e -o pipefail -u

target_dir=$1

# `-t man` is needed for the conditionally rendered sections
sphinx-build -W --keep-going -b man -t man docs/source "$target_dir"
