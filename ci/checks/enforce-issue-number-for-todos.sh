#!/usr/bin/env bash

set -e -o pipefail -u

self_dir=$(cd "$(dirname "$0")" &>/dev/null; pwd -P)
source "$self_dir"/utils.sh

# Negative lookahead (?!...), requires Perl syntax (-P): find fixmes/todos NOT followed by issue number
if git grep -PIin '(\*|//|#|<!--)\s*(fixme|todo)(?! \([[:alnum:]/-]*#[0-9]+\): )'; then
  die "Use 'TODO|FIXME (<other-repo-name-or-empty>#<issue-number>): <short-description>' format for the above TODOs and FIXMEs"
fi
