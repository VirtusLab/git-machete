#!/usr/bin/env bash

set -e -o pipefail -u

self_dir=$(cd "$(dirname "$0")" &>/dev/null; pwd -P)
source "$self_dir"/utils.sh
self_name=$(basename "$0")

if git grep -n Gitlab -- :!**/$self_name; then
  die "Please use 'GitLab' instead of 'Gitlab'."
fi
