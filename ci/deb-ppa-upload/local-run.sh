#!/usr/bin/env bash

set -e -o pipefail -u

cd "$(git rev-parse --show-toplevel)"/ci/deb-ppa-upload/

cat gpg-ssh.env | while read -r var; do
  [[ -n ${!var-} ]] || { echo "Var $var is missing from the environment"; exit 1; }
done

set -x

bash ../export-hash.sh deb-ppa-upload

docker-compose build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" deb-ppa-upload
docker-compose run -e TARGET_DISTRO_NAME=bionic -e TARGET_DISTRO_NUMBER=18.04 -e DO_DPUT=false deb-ppa-upload
docker-compose run -e TARGET_DISTRO_NAME=focal  -e TARGET_DISTRO_NUMBER=20.04 -e DO_DPUT=false deb-ppa-upload
