#!/usr/bin/env bash

set -e -o pipefail -u -x

tag=v$(cut -d\' -f2 git_machete/__init__.py)
# Note that this will also create a git tag on the remote
# (since apparently all non-draft releases on GitHub must have a corresponding git tag).
gh release create "$tag" \
  --title "$tag" \
  --notes "$(sed '5,/^$/!d; /^$/d' RELEASE_NOTES.md)"
