#!/usr/bin/env bash

set -e -o pipefail -u

file=completion/git-machete.fish
if ! [[ -f $file ]]; then
  echo "Fish completion file does not exist under the expected path ($file)"
  exit 1
fi

if grep -Pn 'not __fish_seen_subcommand_from .*?--([a-zA-Z0-9-]+)[^a-zA-Z0-9-].*? -x.*? -l \1 .*?-a ' $file; then
  echo
  echo "In fish completion ($file), flags with required parameter (-x) should not use \`not __fish_seen_subcommand_from <OPTION>\`."
  echo 'If they do, as of fish v4.1.0, their parameter is not completed (-a) when the flag is used without `=` (`--foo <TAB>`).'
  exit 1
fi
