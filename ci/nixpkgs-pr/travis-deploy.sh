#!/usr/bin/env bash

set -e -o pipefail -u -x

DIRECTORY_HASH=$(git rev-parse HEAD:ci/nixpkgs-pr)
export DIRECTORY_HASH
cd ci/nixpkgs-pr/

[[ -n $TRAVIS_TAG ]]
VERSION=${TRAVIS_TAG#v}
export VERSION

# If the image corresponding to the current state of ci/nixpkgs-pr/ is missing, build it and push to Docker Hub.
docker-compose pull nixpkgs-pr || {
  docker-compose build nixpkgs-pr
  # Unlike in ci/tox/travis-install.sh, we have a guarantee here that this script won't be launched for builds coming from forks (it's only being run on tags).
  # Hence, DOCKER_USERNAME and DOCKER_PASSWORD will always be defined.
  echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
  # In case the push fails due to e.g. timeouts (which unfortunately happen on CI), we don't want to fail the entire deployment.
  docker-compose push nixpkgs-pr || true
}

docker-compose up --exit-code-from=nixpkgs-pr nixpkgs-pr
