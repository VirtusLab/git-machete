#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -E -n 'github-mr|gitlab-pr' :!ci/checks/; then
  echo
  echo 'GitHub has PRs, GitLab has MRs - is it a copy-paste error?'
  exit 1
fi
