#!/usr/bin/env bash

set -e -o pipefail -u

self_name=$(basename "$0")

if git grep -n '[fF]orkpoint' -- :!**/$self_name; then
  echo "Please use 'fork point' or 'Fork point' or 'fork_point' instead of 'forkpoint' or 'Forkpoint'."
  exit 1
fi
