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

git clone https://${GITHUB_TOKEN}@github.com/VirtusLab/homebrew-git-machete.git ../homebrew-git-machete
cd ../homebrew-git-machete/

git config user.email "gitmachete@virtuslab.com"
git config user.name "Git Machete Release Bot"
sha256=$(
  curl -s https://$pypi_host/pypi/git-machete/$version/json \
  | jq --raw-output '.urls | map(select(.packagetype == "sdist")) | .[0].digests.sha256')
sed -i "s/git-machete-.*\.tar\.gz/git-machete-$version.tar.gz/" git-machete.rb
sed -i "s/pypi.io/$pypi_host/" git-machete.rb
sed -i "s/^  sha256 .*/  sha256 \"$sha256\"/" git-machete.rb
git add git-machete.rb
git commit --message "Release $version, CircleCI build: $CIRCLE_BUILD_NUM"

if [[ $do_push == true ]]; then
  git push origin master
else
  echo "Refraining from push since it's a dry run"
  sed -i "s/pypi.io/$pypi_host/" git-machete.rb
  # install git-machete from local formula with homebrew
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" < /dev/null
  echo 'eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"' >> /home/circleci/.bash_profile
  eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
  brew install ./git-machete.rb
fi
