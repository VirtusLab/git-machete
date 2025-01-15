#!/usr/bin/env bash

set -e -o pipefail -u

today=$(date +%Y-%m-%d)
if git grep -n "$today" -- tests/; then
  echo
  echo "Is current date ($today) used in expected test outputs? If so, then the test will likely fail on another day."
  echo "Use \`self.patch_symbol(mocker, 'git_machete.utils.get_current_date', lambda: '2023-12-31')\` instead."
  exit 1
fi
