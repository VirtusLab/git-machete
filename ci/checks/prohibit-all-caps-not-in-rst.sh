#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -n 'NO' -- '*.rst'; then
  echo
  echo "Don't use all caps 'NO(T)' in RST files. Use bolded '**no(t)**' instead."
  exit 1
fi
