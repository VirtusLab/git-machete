#!/usr/bin/env bash

set -e -o pipefail -u

current_version=$(python3 setup.py --version)
release_notes_version=$(sed '3!d' RELEASE_NOTES.md | grep -Eo '(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)')

if [[ $current_version != "$release_notes_version" ]]; then
  echo "Please update RELEASE_NOTES.md! Current version: $current_version, latest version in RELEASE_NOTES.md (line 3): $release_notes_version."
  exit 1
fi
