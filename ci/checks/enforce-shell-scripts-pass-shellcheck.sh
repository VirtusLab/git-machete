#!/usr/bin/env bash

set -e -o pipefail -u

# Excluded checks (see https://www.shellcheck.net/wiki/SC<id>):
#   SC2016 - "Expressions don't expand in single quotes"; we intentionally pass literal `$var` strings to awk/sed/ssh/etc. for the remote shell to expand.
#   SC2086 - "Double quote to prevent globbing and word splitting"; we deliberately leave some expansions unquoted to let the shell word-split flag lists.
#   SC2090 - "Quotes/backslashes in this variable will not be respected"; companion to SC2089, triggered by the same intentional unquoted-args patterns.
#   SC2125 - "Brace expansions and globs are literal in assignments"; we assign glob patterns to variables and expand them later at the use site on purpose.
{ git grep --name-only '#!.*sh$' -- ':!*.md' ':!*.fish' ':!*.zsh'; git ls-files '*.sh'; } \
  | sort --unique \
  | xargs shellcheck --check-sourced --exclude=SC2016,SC2086,SC2090,SC2125 --severity=info --shell=bash
