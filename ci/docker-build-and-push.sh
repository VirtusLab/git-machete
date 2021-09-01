#!/usr/bin/env bash

set -e -o pipefail -u -x
image_name=$1

DIRECTORY_HASH=$(git rev-parse HEAD:ci/$image_name)
export DIRECTORY_HASH
cd ci/$image_name/

# If image is not found by pull, build the image and push it to the Docker Hub.
docker-compose --ansi never pull $image_name
# A very unpleasant workaround for https://github.com/docker/compose/issues/7258
# (since v1.25.1, `docker-compose pull` is NOT failing when it can't fetch the image).
image_tag=$(docker-compose --ansi never config | yq eval ".services.$image_name.image" -)
docker image inspect "$image_tag" &>/dev/null || {
  docker-compose --ansi never build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" $image_name
  # In builds coming from forks, secret vars are unavailable for security reasons; hence, we have to skip pushing the newly built image.
  if [[ ${DOCKER_PASSWORD-} && ${DOCKER_USERNAME-} ]]; then
    echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
    # In case the push fails due to e.g. timeouts (which unfortunately sometimes happen on CI), we don't want to fail the entire deployment.
    docker-compose --ansi never push $image_name || true
  fi
}


