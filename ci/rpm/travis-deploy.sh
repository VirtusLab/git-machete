#!/usr/bin/env bash

set -e -o pipefail -u -x

DIRECTORY_HASH=$(git rev-parse HEAD:ci/rpm)
export DIRECTORY_HASH
cd ci/rpm/

# If the image corresponding to the current state of ci/rpm/ is missing, build it and push to Docker Hub.
docker-compose pull rpm || {
  # Unlike in ci/tox/travis-install.sh, we have a guarantee here that this script won't be launched for builds coming from forks (it's only being run on tags).
  # Hence, DOCKER_USERNAME and DOCKER_PASSWORD will always be defined.
  docker-compose build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" rpm
  echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
  docker-compose push rpm
}

docker-compose up --exit-code-from=rpm rpm
