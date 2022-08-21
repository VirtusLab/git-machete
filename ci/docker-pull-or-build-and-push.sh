#!/usr/bin/env bash

set -e -o pipefail -u

image_name=$1

source "$(git rev-parse --show-toplevel)"/ci/ci-run-commons.sh
docker_compose_pull_or_build_and_push "$image_name"
