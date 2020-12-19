#!/usr/bin/env bash

set -e -o pipefail -u

# Downtime of the linked websites shouldn't block a release.
if [[ ${TRAVIS_BRANCH-} != master ]]; then
  extra_options='--use=lint-no-dead-urls'
else
  extra_options=''
fi

remark --use=validate-links $extra_options --ignore-path=.gitignore  --frail .
