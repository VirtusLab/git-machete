#!/usr/bin/env bash

set -e -o pipefail -u

remark . --ignore-path=.gitignore --use=remark-validate-links --frail
