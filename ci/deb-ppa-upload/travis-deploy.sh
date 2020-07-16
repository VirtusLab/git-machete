#!/usr/bin/env bash

set -e -o pipefail -u -x

DIRECTORY_HASH=$(git rev-parse HEAD:ci/deb-ppa-upload)
export DIRECTORY_HASH
cd ci/deb-ppa-upload/

# If the image corresponding to the current state of ci/deb-ppa-upload/ is missing, build it and push to Docker Hub.
docker-compose pull deb-ppa-upload || {
  docker-compose build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" deb-ppa-upload
  # Unlike in ci/tox/travis-install.sh, we have a guarantee here that this script won't be launched for builds coming from forks (it's only being run on master).
  # Hence, DOCKER_USERNAME and DOCKER_PASSWORD will always be defined.
  echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
  # In case the push fails due to e.g. timeouts (which unfortunately sometimes happen on CI), we don't want to fail the entire deployment.
  docker-compose push deb-ppa-upload || true
}

docker-compose run -e TARGET_DISTRO_NAME=bionic -e TARGET_DISTRO_NUMBER=18.04 deb-ppa-upload
docker-compose run -e TARGET_DISTRO_NAME=focal  -e TARGET_DISTRO_NUMBER=20.04 deb-ppa-upload
