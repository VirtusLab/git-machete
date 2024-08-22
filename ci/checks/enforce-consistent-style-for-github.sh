#!/usr/bin/env bash

set -e -o pipefail -u

self_name=$(basename "$0")

if git grep -n Github -- :!**/$self_name; then
  echo "Please use 'GitHub' instead of 'Github'."
  exit 1
fi
