#!/usr/bin/env bash

set -e -o pipefail -u -x

DIRECTORY_HASH=$(git rev-parse HEAD:ci/rpm)
export DIRECTORY_HASH
cd ci/rpm/

# If the image corresponding to the current state of ci/rpm/ is missing, build it and push to Docker Hub.
docker-compose pull rpm || {
  # Unlike in ci/tox/travis-install.sh, we have a guarantee here that this script won't be launched for builds coming from forks (it's only being run on master).
  # Hence, DOCKER_USERNAME and DOCKER_PASSWORD will always be defined.
  docker-compose build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" rpm
  echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
  # In case the push fails due to e.g. timeouts (which unfortunately sometimes happen on CI), we don't want to fail the entire deployment.
  docker-compose push rpm || true
}

docker-compose run rpm
