#!/usr/bin/env bash

set -e -o pipefail -u

last_tag=$(git describe --tags --abbrev=0)
last_tag_version=${last_tag/v/}
current_version=$(python3 setup.py --version)

if [[ "$(echo -e "$current_version\n$last_tag_version" | sort --version-sort | tail -n 1)" == "$last_tag_version" ]]; then
  echo "Please increment version with new release! Last released version: $last_tag_version"
  exit 1
fi
