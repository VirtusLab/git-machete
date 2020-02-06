#!/usr/bin/env bash

set -e -o pipefail -u -x

DIRECTORY_HASH=$(git rev-parse HEAD:ci/apt-ppa-upload)
export DIRECTORY_HASH
cd ci/apt-ppa-upload/

# If the image corresponding to the current state of ci/apt-ppa-upload/ is missing, build it and push to Docker Hub.
docker-compose pull apt-ppa-upload || {
  docker-compose build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" apt-ppa-upload
  # Unlike in ci/tox/travis-install.sh, we have a guarantee here that this script won't be launched for builds coming from forks (it's only being run on tags).
  # Hence, DOCKER_USERNAME and DOCKER_PASSWORD will always be defined.
  echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
  # In case the push fails due to e.g. timeouts (which unfortunately happen on CI), we don't want to fail the entire deployment.
  docker-compose push apt-ppa-upload || true
}

docker-compose up --exit-code-from=apt-ppa-upload apt-ppa-upload
