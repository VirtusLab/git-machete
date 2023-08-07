#!/usr/bin/env bash

set -e -o pipefail -u

remark . --ignore-path=.gitignore --use=remark-validate-links --frail
# The check for dead URLs has a relatively low importance, and turned out to be very flaky.
# Let's make it non-blocking.
remark . --ignore-path=.gitignore --use=remark-lint-no-dead-urls
