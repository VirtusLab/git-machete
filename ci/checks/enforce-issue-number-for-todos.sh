#!/usr/bin/env bash

set -e -o pipefail -u

# Negative lookahead (?!...), requires Perl syntax (-P): find fixmes/todos NOT followed by issue number
if git grep --perl-regexp -I --ignore-case --line-number '(\*|//|#|<!--)\s*(fixme|todo)(?! \([[:alnum:]/-]*#[0-9]+\): )'; then
  echo "Use 'TODO|FIXME (<other-repo-name-or-empty>#<issue-number>): <short-description>' format for the above TODOs and FIXMEs"
  exit 1
fi
