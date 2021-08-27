#!/usr/bin/env bash

set -e -o pipefail -u -x

if [[ ${1-} == "--dry-run" || ${CIRCLE_BRANCH-} != "master" ]]; then
  do_dput=false
else
  do_dput=true
fi

bash ci/docker-build-and-push.sh deb-ppa-upload

docker-compose --ansi never run -e TARGET_DISTRO_NAME=bionic -e TARGET_DISTRO_NUMBER=18.04 -e DO_DPUT=$do_dput deb-ppa-upload
docker-compose --ansi never run -e TARGET_DISTRO_NAME=focal  -e TARGET_DISTRO_NUMBER=20.04 -e DO_DPUT=$do_dput deb-ppa-upload
