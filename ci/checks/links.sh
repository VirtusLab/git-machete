#!/usr/bin/env bash

# Downtime of the linked websites shouldn't block a release.
[[ $TRAVIS_BRANCH = master ]] && exit 0

set -e -o pipefail -u

# Not passing `-I`/`--head` flag to `curl` since medium.com sometimes responds with 405 Method Not Allowed (sometimes with 200 OK, though).
git ls-files ':!ci/' ':!hook_samples/' \
| xargs grep -ho "https://[^]')\" ]*" \
| sort -u \
| xargs -t -l curl -Lfs --max-time 30 -o/dev/null -w "> %{http_code}\n" || {
  echo "Some of the links found in the codebase did not return 2xx HTTP status, please fix"
  exit 1
}
