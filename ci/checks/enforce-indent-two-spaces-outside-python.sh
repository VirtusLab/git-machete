#!/usr/bin/env bash

set -e -o pipefail -u

self_dir=$(cd "$(dirname "$0")" &>/dev/null; pwd -P)
self_name=$(basename --suffix=.sh "$0")

git ls-files ':!*.awk' ':!/.circleci/config.yml' ':!*/Dockerfile' ':!docs/*' ':!graphics/setup-sandbox' ':!*.md' ':!*.png' ':!*.py' ':!*.svg' \
  | xargs awk -f "$self_dir/$self_name.awk"
