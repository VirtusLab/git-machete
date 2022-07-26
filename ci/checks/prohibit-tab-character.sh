#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -In $'\t' -- ':!debian/rules' ':!*.svg'; then
  echo 'The above lines contain tab character (instead of spaces), please tidy up'
  exit 1
fi
