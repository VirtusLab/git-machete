#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -n -P '\bsleep\(' -- '*.py' ':!tests/mockers.py'; then
  echo
  echo 'Do not use sleep() in Python code outside of tests/mockers.py.'
  echo 'Real-time sleeps make tests slow and flaky (e.g. clock slewing on macOS CI'
  echo 'runners can leave consecutive commits on the same committer-second).'
  echo 'If you need to ensure two consecutive commits land on different'
  echo 'committer-seconds, use tests.mockers.wait_to_bump_commit_timestamp instead.'
  exit 1
fi
