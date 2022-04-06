#!/usr/bin/env bash

set -e -o pipefail -u

self_dir=$(cd "$(dirname "$0")" &>/dev/null; pwd -P)
source "$self_dir"/utils.sh

if git grep -we Github -- :^ci/checks/ensure-consistent-style-for-github.sh; then
  die "Please use 'GitHub' instead of 'Github'."
fi
