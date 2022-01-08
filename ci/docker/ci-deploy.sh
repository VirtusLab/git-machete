#!/usr/bin/env bash

set -e -o pipefail -u -x

if [[ ${1-} == "--dry-run" || ${CIRCLE_BRANCH-} != "master" ]]; then
  do_push=false
  pypi_host=test.pypi.org
else
  do_push=true
  pypi_host=pypi.org
fi

version=$(grep '__version__ = ' git_machete/__init__.py | cut -d\' -f2)

docker build \
  --build-arg pypi_host=$pypi_host \
  --build-arg version=$version \
  -t gitmachete/git-machete:$version \
  -t gitmachete/git-machete:latest \
  - < ci/docker/Dockerfile

[[ $(docker run gitmachete/git-machete:latest --version) == "git machete version $version" ]]

if [[ $do_push == true ]]; then
  echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
  docker push gitmachete/git-machete:$version
  docker push gitmachete/git-machete:latest
else
  echo "Refraining from push since it's a dry run"
fi
