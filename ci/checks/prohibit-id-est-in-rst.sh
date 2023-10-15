#!/usr/bin/env bash

set -e -o pipefail -u

self_dir=$(cd "$(dirname "$0")" &>/dev/null; pwd -P)
source "$self_dir"/utils.sh

if git grep -En 'i\. ?e\.' -- '*.rst'; then
  die 'Do not use `i.e.` in docs; use a clearer alternative like a long dash `---` instead'
fi
