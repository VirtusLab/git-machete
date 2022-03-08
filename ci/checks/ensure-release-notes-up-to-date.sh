#!/usr/bin/env bash

set -e -o pipefail -u

current_version=$(python3 setup.py --version)
release_notes_version=$(egrep -o '(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)' RELEASE_NOTES.md --max-count 1)

if [[ $current_version != "$release_notes_version" ]]; then
  echo "Please update RELEASE_NOTES! Current version: $current_version, latest version in release notes: $release_notes_version."
  exit 1
fi
