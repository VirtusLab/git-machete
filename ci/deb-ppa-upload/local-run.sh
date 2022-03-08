#!/usr/bin/env bash

set -e -o pipefail -u

source ../local-run-commons.sh deb-ppa-upload
check_env gpg-ssh.env
export_directory_hash deb-ppa-upload
cd "$(git rev-parse --show-toplevel)"/ci/deb-ppa-upload/


set -x
export TARGET=local
export MOUNT_POINT=/home/ci-user
docker-compose build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" deb-ppa-upload
docker-compose run -e TARGET_DISTRO_NAME=bionic -e TARGET_DISTRO_NUMBER=18.04 -e DO_DPUT=false deb-ppa-upload
docker-compose run -e TARGET_DISTRO_NAME=focal  -e TARGET_DISTRO_NUMBER=20.04 -e DO_DPUT=false deb-ppa-upload
