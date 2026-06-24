#!/usr/bin/env bash

set -e -o pipefail -u

# Headers in the docs should NOT be terminated with a colon. This covers:
#  * definition-term headers consisting of an inline literal (optionally followed by a parenthetical),
#    such as config keys (``machete.github.annotateWithUrls``:), subcommand signatures (``create-pr [...]``:)
#    and environment variable names (``GIT_MACHETE_EDITOR``:),
#  * bold section titles such as **Usage:**, **Options:** or **Git config keys:**.
if git grep -nE -e '^``[^`]+``( \(.*\))?:$' -e '^\*\*.*:\*\*$' -- '*.rst'; then
  echo
  echo 'Do not put a trailing colon after a header in the docs (config key, subcommand signature, environment variable name or bold section title).'
  echo 'Drop the colon: a header reads as a label on its own, and the colon is just visual noise.'
  exit 1
fi
