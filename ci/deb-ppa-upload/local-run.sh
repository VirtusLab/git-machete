#!/usr/bin/env bash

set -e -o pipefail -u

source "$(git rev-parse --show-toplevel)"/ci/local-run-commons.sh deb-ppa-upload

export_directory_hash deb-ppa-upload
cd "$(git rev-parse --show-toplevel)"/ci/deb-ppa-upload/
check_env gpg-ssh.env

set -x
docker-compose --progress=plain build deb-ppa-upload
common_flags=(
  -e "GID=$(id -g)"
  -e "UID=$(id -u)"
  -e "DO_DPUT=true"
  -e "GPG_EMAIL=pawel.p.lipski@gmail.com"
  -e "GPG_USERNAME=pawel-lipski-launchpad"
  -e "LAUNCHPAD_USERNAME=pawel-lipski")
docker-compose run -e TARGET_DISTRO_NAME=bionic -e TARGET_DISTRO_NUMBER=18.04 "${common_flags[@]}" deb-ppa-upload
docker-compose run -e TARGET_DISTRO_NAME=focal  -e TARGET_DISTRO_NUMBER=20.04 "${common_flags[@]}" deb-ppa-upload
docker-compose run -e TARGET_DISTRO_NAME=jammy  -e TARGET_DISTRO_NUMBER=22.04 "${common_flags[@]}" deb-ppa-upload
