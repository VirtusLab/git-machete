#!/usr/bin/env bash

set -e -o pipefail -u -x

/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" < /dev/null
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"

if [[ ${1-} == "--dry-run" || ${CIRCLE_BRANCH-} != "master" ]]; then
  do_push=false
  pypi_host=test.pypi.org
else
  do_push=true
  pypi_host=pypi.org
fi

version=$(python3 setup.py --version)
url="https://$pypi_host/packages/source/g/git-machete/git-machete-$version.tar.gz"
sha256=$(
  curl -s https://$pypi_host/pypi/git-machete/"$version"/json \
  | jq --raw-output '.urls | map(select(.packagetype == "sdist")) | .[0].digests.sha256')

git config --global user.email "gitmachete@virtuslab.com"
git config --global user.name "Git Machete Bot"

echo "Bump homebrew formula"
if [[ $do_push == true ]]; then
  brew bump-formula-pr --no-browse --verbose --url "$url" --sha256 "$sha256" git-machete
else
  echo "Refraining from push since it's a dry run"
  brew bump-formula-pr --write-only --no-browse --verbose --url "$url" --sha256 "$sha256" git-machete

  echo "Attempt to install the formula locally"
  attempts=3
  i=1
  while true; do
    if false; then
      echo "xd"
    elif (( i < attempts )); then
      echo "Retrying the installation..."
      i=$((i + 1))
      sleep 30
    else
      echo "Installing the formula locally did not succeed despite $attempts attempts"
      exit 1
    fi
  done

  if [[ "$version" != "$(git machete --version | cut -d' ' -f4)" ]]; then
    echo "Something went wrong during brew installation: installed version does not match version from formula."
    echo "Formula version: $version, installed version: $(git machete --version | cut -d' ' -f4)"
    exit 1
  fi
  brew remove git-machete
fi
