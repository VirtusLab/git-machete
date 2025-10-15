#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -En 'i\. ?e\.' -- '*.rst'; then
  echo 'Do not use `i.e.` in docs; use a clearer alternative like a long dash `---` instead'
  exit 1
fi
