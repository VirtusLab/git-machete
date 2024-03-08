#!/usr/bin/env bash

set -e -o pipefail -u

last_tag=$(git describe --tags --abbrev=0)
last_tag_version=${last_tag/v/}
# Not using `python3 setup.py --version` to make it work in the contexts where setuptools are missing (Python 3.12+)
current_version=$(cut -d\' -f2 git_machete/__init__.py)

if [[ "$(echo -e "$current_version\n$last_tag_version" | sort --version-sort | tail -n 1)" == "$last_tag_version" ]]; then
  echo "Please increment version in git_machete/__init__.py with a new release! Last released version: $last_tag_version"
  exit 1
fi
