#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -Eni 'e\. ?g\.' -- '*.rst'; then
  echo 'Do not use `e.g.`/`E.g.` in docs; use a clearer alternative like `for example` instead'
  exit 1
fi
