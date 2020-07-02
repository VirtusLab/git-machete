#!/usr/bin/env bash

set -e -o pipefail -u -x

git clone https://${GITHUB_TOKEN}@github.com/VirtusLab/homebrew-git-machete.git ../homebrew-git-machete
cd ../homebrew-git-machete/

git config user.email "travis@travis-ci.org"
git config user.name "Travis CI"
VERSION=$(grep '__version__ = ' git_machete/__init__.py | cut -d\' -f2)
sha256=$(curl -s https://pypi.org/pypi/git-machete/$VERSION/json | jq --raw-output '.urls | map(select(.packagetype == "sdist")) | .[0].digests.sha256')
sed -i "s/git-machete-.*\.tar\.gz/git-machete-$VERSION.tar.gz/" git-machete.rb
sed -i "s/^  sha256 .*/  sha256 \"$sha256\"/" git-machete.rb
git add git-machete.rb
git commit --message "Release $VERSION, Travis build: $TRAVIS_BUILD_NUMBER"
git push origin master
