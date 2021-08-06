#!/usr/bin/env bash

set -e -o pipefail -u

exit_code=0

last_tag=$(git describe --tags --abbrev=0)
last_tag_version=${last_tag:1}
current_version=$(grep '__version__ = ' git_machete/__init__.py | cut -d\' -f2)

if [[ "$(printf "$current_version\n$last_tag_version" | sort -V -r | head -n 1)" == "$last_tag_version" ]]; then
  echo "Please Increment version with new release! Last released version: $last_tag_version"
  exit_code=1
fi

exit $exit_code
