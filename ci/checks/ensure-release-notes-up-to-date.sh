#!/usr/bin/env bash

set -e -o pipefail -u

current_version=$(grep '__version__ = ' git_machete/__init__.py | cut -d\' -f2)
release_notes_version=$(awk -F"## New in git-machete " '/## New in git-machete /{print $2;exit;}' RELEASE_NOTES.md)

if [[ "$(printf "$current_version\n$release_notes_version" | sort --version-sort | tail -n 1)" != "$release_notes_version" ]]; then
  echo "Please update RELEASE_NOTES! Current version: $current_version, latest version in release notes: $release_notes_version"
  exit 1
fi
