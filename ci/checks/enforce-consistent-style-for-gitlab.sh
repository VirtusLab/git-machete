#!/usr/bin/env bash

set -e -o pipefail -u

self_name=$(basename "$0")

if git grep -n Gitlab -- :!**/$self_name; then
  echo "Please use 'GitLab' instead of 'Gitlab'."
  exit 1
fi
