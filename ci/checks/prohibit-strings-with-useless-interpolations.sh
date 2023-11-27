#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -n "f'{[^{]*}'" -- '*.py' || git grep -n 'f"{[^{]*}"'  -- '*.py'; then
  echo 'The above lines apparently contain a useless string interpolation that spans over the entire string.'
  echo 'Unwrap the expressions from both the interpolation and the outer string.'
  exit 1
fi
