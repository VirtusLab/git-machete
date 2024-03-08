#!/usr/bin/env bash

set -e -o pipefail -u

self_dir=$(cd "$(dirname "$0")" &>/dev/null; pwd -P)
source "$self_dir"/utils.sh

if git grep -n 'split(.\\n.)' -- '*.py'; then
  die 'Do not use split("\\n") on strings as it does not cover \\r\\n line breaks; use splitlines() instead'
fi
