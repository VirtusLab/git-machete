#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -EIn 'PR|-pr($|[^o])|[pP]ull [rR]equest' -- '*gitlab*' :!ci/checks/; then
  echo
  echo "GitLab uses *merge* requests rather than *pull* requests, please fix"
  echo 'Usage of `pull_request` in GitLab-related identifiers is allowed so that we avoid inventing a common abstract word for pull and merge requests'
  exit 1
fi
