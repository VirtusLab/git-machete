#!/usr/bin/env bash

set -e -o pipefail -u

current_version=$(grep '__version__ = ' git_machete/__init__.py | cut -d\' -f2)
release_notes_version=$(egrep -o '(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?' RELEASE_NOTES.md --max-count 1)

if [[ "$(printf "$current_version\n$release_notes_version" | sort --version-sort | tail -n 1)" != "$release_notes_version" ]]; then
  echo "Please update RELEASE_NOTES! Current version: $current_version, latest version in release notes: $release_notes_version"
  exit 1
fi
