#!/usr/bin/env bash

set -e -o pipefail -u -x

if [[ ${1-} == "--dry-run" || ${CIRCLE_BRANCH-} != "master" ]]; then
  do_dput=false
else
  do_dput=true
fi

source "$(git rev-parse --show-toplevel)"/ci/ci-run-commons.sh

docker_compose_pull_or_build_and_push deb-ppa-upload
common_flags=(
  -e "DO_DPUT=$do_dput"
  -e "GPG_EMAIL=plipski@virtuslab.com"
  -e "GPG_USERNAME=Pawel Lipski"
  -e "LAUNCHPAD_USERNAME=virtuslab")
docker-compose --ansi=never run -e TARGET_DISTRO_NAME=bionic -e TARGET_DISTRO_NUMBER=18.04 "${common_flags[@]}" deb-ppa-upload
docker-compose --ansi=never run -e TARGET_DISTRO_NAME=focal  -e TARGET_DISTRO_NUMBER=20.04 "${common_flags[@]}" deb-ppa-upload
docker-compose --ansi=never run -e TARGET_DISTRO_NAME=jammy  -e TARGET_DISTRO_NUMBER=22.04 "${common_flags[@]}" deb-ppa-upload
