#!/usr/bin/env bash

set -e -o pipefail -u -x

DOCKER_TAG=$(git rev-parse HEAD:ci/apt-ppa/)
export DOCKER_TAG
cd ci/apt-ppa/

# If the image corresponding to the current state of ci/apt-ppa/ is missing, build it and push to Docker Hub.
docker-compose pull ppa-upload || {
  docker-compose build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" ppa-upload
  echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
  docker-compose push ppa-upload
}

docker-compose up --exit-code-from=ppa-upload ppa-upload
