#!/usr/bin/env bash

set -e -o pipefail -u

if [[ ${1-} == "--dry-run" || ${CIRCLE_BRANCH-} != "master" ]]; then
  do_push=false
else
  do_push=true
fi

version=$(grep '__version__ = ' git_machete/__init__.py | cut -d\' -f2)

docker build \
  -t gitmachete/git-machete:$version \
  -t gitmachete/git-machete:latest \
  -f ci/docker/Dockerfile .

[[ $(docker run gitmachete/git-machete:latest --version) == "git machete version $version" ]]

if [[ $do_push == true ]]; then
  echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
  docker push gitmachete/git-machete:$version
  docker push gitmachete/git-machete:latest
else
  echo "Refraining from push since it's a dry run"
fi
