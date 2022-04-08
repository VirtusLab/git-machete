#!/usr/bin/env bash

set -e -o pipefail -u

self_dir=$(cd "$(dirname "$0")" &>/dev/null; pwd -P)
source "$self_dir"/utils.sh

if git grep '[fF]orkpoint' -- :^ci/checks/ensure-consistent-style-for-fork-point.sh; then
  die "Please use 'fork point' or 'Fork point' or 'fork_point' instead of 'forkpoint' or 'Forkpoint'."
fi
