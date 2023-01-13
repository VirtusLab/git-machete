#!/usr/bin/env bash

set -e -o pipefail -u

function check_var() {
  if [[ ${!1-} ]]; then return 0; fi
  [[ -f .env ]] || { echo "Var $1 missing from environment and no .env file found; see .env.sample file"; return 1; }
  grep -q "^$1=" .env || { echo "Var $1 missing both from environment and .env file"; return 1; }
}

function check_env() {
  cat $1 | while read -r var; do
    [[ -n ${!var-} ]] || { echo "Var $var is missing from the environment"; exit 1; }
  done
}

function export_directory_hash() {
  hash=$(git rev-parse HEAD:ci/$1)
  if git diff-index --quiet HEAD .; then
    export DIRECTORY_HASH="$hash"
  else
    export DIRECTORY_HASH="$hash"-dirty
  fi
}
