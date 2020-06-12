#!/usr/bin/env bash

set -e -o pipefail -u -x

tag=v$(grep '__version__ = ' git_machete/__init__.py | cut -d\' -f2)
# Note that this will also create a git tag on the remote
# (since apparently all non-draft releases on GitHub must have a corresponding git tag).
hub release create "$tag" \
  --message "$tag"$'\n\n'"$(sed '4,/^$/!d; /^$/d' RELEASE_NOTES.md)" \
  --attach dist/git-machete-*.noarch.rpm
