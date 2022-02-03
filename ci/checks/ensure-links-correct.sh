#!/usr/bin/env bash

set -e -o pipefail -u

# Downtime of the linked websites shouldn't block a release.
if [[ ${CIRCLE_BRANCH-} != master ]]; then
  extra_options='--rc-path=.remarkrc.yml'
else
  extra_options='--rc-path=.remarkrc_master.yml'
fi

remark $extra_options --ignore-path=.gitignore  --frail .
