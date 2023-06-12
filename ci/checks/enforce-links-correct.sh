#!/usr/bin/env bash

set -e -o pipefail -u

# Downtime of the linked websites shouldn't block a release.
if [[ ${CIRCLE_BRANCH-} != master ]]; then
  rc_path=.remarkrc.yml
else
  rc_path=.remarkrc-allow-dead-urls.yml
fi

# This check has a relatively low importance, and turned out to be very flaky.
# Let's make it non-blocking.
remark --frail --ignore-path=.gitignore --rc-path=$rc_path . || true
