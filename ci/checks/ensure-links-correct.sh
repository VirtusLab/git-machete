#!/usr/bin/env bash

set -e -o pipefail -u

# Downtime of the linked websites shouldn't block a release.
if [[ ${CIRCLE_BRANCH-} != master ]]; then
  rc_path=.remarkrc.yml
else
  rc_path=.remarkrc_master.yml
fi

remark --frail --ignore-path=.gitignore --rc-path=$rc_path .
