#!/usr/bin/env bash

set -e -o pipefail -u -x

source "$(git rev-parse --show-toplevel)"/ci/local-run-commons.sh

export_directory_hash aur
cd "$(git rev-parse --show-toplevel)"/ci/aur/

git_revision=$(git rev-parse "@{upstream}")
docker-compose --progress=plain build aur
docker-compose run -e GIT_REVISION="$git_revision" aur
