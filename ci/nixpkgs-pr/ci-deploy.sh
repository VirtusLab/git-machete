#!/usr/bin/env bash

set -e -o pipefail -u -x

if [[ ${1-} == "--dry-run" || ${CIRCLE_BRANCH-} != "master" ]]; then
  do_push=false
  pypi_host=test.pypi.org
else
  do_push=true
  pypi_host=pypi.org
fi

DIRECTORY_HASH=$(git rev-parse HEAD:ci/nixpkgs-pr)
export DIRECTORY_HASH

VERSION=$(grep '__version__ = ' git_machete/__init__.py | cut -d\' -f2)
export VERSION

cd ci/nixpkgs-pr/

# If the image corresponding to the current state of ci/nixpkgs-pr/ is missing, build it and push to Docker Hub.
docker-compose pull nixpkgs-pr
# A very unpleasant workaround for https://github.com/docker/compose/issues/7258
# (since v1.25.1, `docker-compose pull` is NOT failing when it can't fetch the image).
image_tag=$(docker-compose config | yq eval '.services.nixpkgs-pr.image' -)
docker image inspect "$image_tag" &>/dev/null || {
  docker-compose build nixpkgs-pr
  # Unlike in ci/tox/ci-run.sh, we have a guarantee here that this script won't be launched for builds coming from forks (it's only being run on master).
  # Hence, DOCKER_USERNAME and DOCKER_PASSWORD will always be defined.
  echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
  # In case the push fails due to e.g. timeouts (which unfortunately sometimes happen on CI), we don't want to fail the entire deployment.
  docker-compose push nixpkgs-pr || true
}

docker-compose run -e DO_PUSH=$do_push -e PYPI_HOST=$pypi_host nixpkgs-pr
