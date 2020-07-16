#!/usr/bin/env bash

set -e -o pipefail -u

cd "$(git rev-parse --show-toplevel)"/ci/deb-ppa-upload/

cat gpg-ssh.env | while read -r var; do
  [[ -n ${!var-} ]] || { echo "Var $var is missing from the environment"; exit 1; }
done

set -x

hash=$(git rev-parse HEAD:ci/deb-ppa-upload)
if git diff-index --quiet HEAD .; then
  export DIRECTORY_HASH="$hash"
else
  export DIRECTORY_HASH="$hash"-dirty
fi

docker-compose build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" deb-ppa-upload
docker-compose run -e TARGET_DISTRO_NAME=bionic -e TARGET_DISTRO_NUMBER=18.04 deb-ppa-upload
docker-compose run -e TARGET_DISTRO_NAME=focal  -e TARGET_DISTRO_NUMBER=20.04 deb-ppa-upload
