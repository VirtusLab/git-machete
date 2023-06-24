#!/usr/bin/env bash

set -e -o pipefail -u

{ git grep --name-only '#!.*sh$' -- ':!*.md' ':!*.fish' ':!*.zsh'; git ls-files '*.sh'; } \
  | sort --unique \
  | xargs shellcheck --check-sourced --exclude=SC1090,SC1091,SC2016,SC2086,SC2090,SC2125 --severity=info --shell=bash
