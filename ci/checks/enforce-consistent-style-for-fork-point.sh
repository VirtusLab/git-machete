#!/usr/bin/env bash

set -e -o pipefail -u

self_dir=$(cd "$(dirname "$0")" &>/dev/null; pwd -P)
self_name=$(basename "$0")
source "$self_dir"/utils.sh

if git grep -n '[fF]orkpoint' -- :!**/$self_name; then
  die "Please use 'fork point' or 'Fork point' or 'fork_point' instead of 'forkpoint' or 'Forkpoint'."
fi
