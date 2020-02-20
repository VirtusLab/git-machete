#!/usr/bin/env bash

# Downtime of the linked the websites shouldn't block a release or a master build.
[[ $TRAVIS_TAG ]] && exit 0
[[ $TRAVIS_BRANCH = master ]] && exit 0

set -e -o pipefail -u

git ls-files | grep -v '^ci/' | xargs grep -ho "https://[^]') ]*" | sort -u | xargs -t -l curl -LfsI --max-time 30 -o/dev/null -w "> %{http_code}\n" || {
  echo "Some of the links found in the codebase did not return 2xx HTTP status, please fix"
  exit 1
}
