#!/usr/bin/env bash

if git grep -n -e ' `[^`]' --and --not -e 'https://' -- '*.rst'; then
  echo
  echo 'Single backticks (`...`) are notoriously confusing in ReStructuredText: unlike in Markdown, they correspond to italics, not verbatim text.'
  echo 'Use the somewhat more unambiguous *...* for italics, and double backticks (``...``) for verbatim text.'
  exit 1
fi
