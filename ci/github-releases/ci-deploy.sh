#!/usr/bin/env bash

set -e -o pipefail -u -x

tag=v$(python3 setup.py --version)
# Note that this will also create a git tag on the remote
# (since apparently all non-draft releases on GitHub must have a corresponding git tag).
hub release create "$tag" \
  --message="$tag"$'\n\n'"$(sed '5,/^$/!d; /^$/d' RELEASE_NOTES.md)" \
  --attach="$(echo dist/git-machete-*.noarch.rpm)"
