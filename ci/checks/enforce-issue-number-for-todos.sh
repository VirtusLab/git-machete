#!/usr/bin/env bash

function error() {
  red='\033[91m'
  endc='\033[0m'

  if [[ $# -ge 1 ]]; then
    if [[ -t 1 ]]; then
      echo -e "${red}>>> $@ <<<${endc}"
    else
      echo -e ">>> $@ <<<"
    fi
  fi
}

function die() {
  echo
  error "$@"
  echo
  exit 1
}

# Negative lookahead (?!...), requires Perl syntax (-P): find fixmes/todos NOT followed by issue number
if git grep -PIin '(\*|//|#|<!--)\s*(fixme|todo)(?! \([[:alnum:]/-]*#[0-9]+\): )'; then
  die "Use 'TODO|FIXME (<other-repo-name-or-empty>#<issue-number>): <short-description>' format for the above TODOs and FIXMEs"
fi
