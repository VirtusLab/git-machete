#!/usr/bin/env bash

set -e -o pipefail -u

if yq --exit-status eval '.jobs.*.steps[] | select(has("deploy"))' .circleci/config.yml 2>/dev/null; then
  echo
  echo 'The `deploy` step is deprecated (https://circleci.com/docs/2.0/configuration-reference/#deploy-deprecated) and does NOT mask the values of secret environment variables!'
  echo 'Use `run` step for the sake of security.'
  exit 1
fi
