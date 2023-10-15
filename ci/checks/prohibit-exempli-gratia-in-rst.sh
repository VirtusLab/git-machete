#!/usr/bin/env bash

set -e -o pipefail -u

self_dir=$(cd "$(dirname "$0")" &>/dev/null; pwd -P)
source "$self_dir"/utils.sh

if git grep -En 'e\. ?g\.' -- '*.rst'; then
  die 'Do not use `e.g.` in docs; use a clearer alternative like `for example` instead'
fi
