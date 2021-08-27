#!/usr/bin/env bash

set -e -o pipefail -u

image_name=$1

hash=$(git rev-parse HEAD:ci/$image_name)
if git diff-index --quiet HEAD .; then
  export DIRECTORY_HASH="$hash"
else
  export DIRECTORY_HASH="$hash"-dirty
fi