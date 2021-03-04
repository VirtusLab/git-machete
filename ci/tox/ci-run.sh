#!/usr/bin/env bash

set -e -o pipefail -u -x

DIRECTORY_HASH=$(git rev-parse HEAD:ci/tox)
export DIRECTORY_HASH
cd ci/tox/

# If there is no cached image for the expected Git&Python versions and the current state of ci/tox,
# build the image and push it to the Docker Hub.
docker-compose pull tox
# A very unpleasant workaround for https://github.com/docker/compose/issues/7258
# (since v1.25.1, `docker-compose pull` is NOT failing when it can't fetch the image).
image_tag=$(docker-compose config | yq eval '.services.tox.image' -)
docker image inspect "$image_tag" &>/dev/null || {
  docker-compose build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" tox
  # In builds coming from forks, secret vars are unavailable for security reasons; hence, we have to skip pushing the newly built image.
  if [[ ${DOCKER_PASSWORD-} && ${DOCKER_USERNAME-} ]]; then
    echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
    docker-compose push tox
  fi
}

docker-compose run tox
