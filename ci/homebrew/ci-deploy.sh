#!/usr/bin/env bash

set -e -o pipefail -u

if [[ ${1-} == "--dry-run" || ${CIRCLE_BRANCH-} != "master" ]]; then
  do_push=false
  pypi_host=test.pypi.org
else
  do_push=true
  pypi_host=pypi.org
fi

version=$(python3 setup.py --version)
url="https://pypi.org/packages/source/g/git-machete/git-machete-$version.tar.gz"
sha256=$(
  curl -s https://$pypi_host/pypi/git-machete/$version/json \
  | jq --raw-output '.urls | map(select(.packagetype == "sdist")) | .[0].digests.sha256')

if [[ $do_push == true ]]; then
  brew brew bump-formula-pr --url $url --sha256 $sha256 git-machete
else
  echo "Refraining from push since it's a dry run"
  brew bump-formula-pr --dry-run --url $url --sha256 $sha256 git-machete
fi
