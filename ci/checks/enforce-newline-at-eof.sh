#!/usr/bin/env bash

set -e -o pipefail -u

found=0
for file in $(git grep -I --files-with-matches ''); do
  last_two_characters=$(tail -c2 "$file" | xxd -p)
  if [[ $last_two_characters == 0a0a ]]; then
    echo "$file (more than one newline character at EOF)"
    found=1
  elif [[ $last_two_characters != *0a ]]; then
    echo "$file (no newline character at EOF)"
    found=1
  fi
done

if [[ $found -ne 0 ]]; then
  echo 'The above non-binary file(s) do not end with a single newline character, please tidy up'
  exit 1
fi
