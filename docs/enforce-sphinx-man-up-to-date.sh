#!/usr/bin/env bash

set -e -o pipefail -u

./docs/generate-sphinx-man.sh docs/man-compare
# Skip `.TH "GIT-MACHETE" "1" "<date>" "" "git-machete"` lines as they might differ just on the date
if ! cmp -s <(grep -v '^\.TH' docs/man/git-machete.1) <(grep -v '^\.TH' docs/man-compare/git-machete.1); then
  echo "Man page is not up-to-date with the sources. Please regenerate via 'tox -e sphinx-man'."
  exit 1
fi
