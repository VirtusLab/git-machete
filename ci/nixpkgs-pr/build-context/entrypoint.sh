#!/usr/bin/env bash

set -e -o pipefail -u

git init
git remote add NixOS https://github.com/NixOS/nixpkgs.git
git remote add VirtusLab https://${GITHUB_TOKEN}@github.com/VirtusLab/nixpkgs.git

set -x
git fetch --progress NixOS master
git checkout -B master NixOS/master

expression_path=pkgs/applications/version-management/git-and-tools/git-machete/default.nix
pypi_url=$(
    curl -s https://pypi.org/pypi/git-machete/v$VERSION/json \
    | jq --raw-output '.urls | map(select(.packagetype == "sdist")) | .[0].url'
)
tarball_sha256=$(nix-prefetch-url --type sha256 "$pypi_url")
existing_version=$(grep 'version = \".*\";' $expression_path | cut -d '"' -f2)
sed -i "s/version = \".*\";/version = \"$VERSION\";/" $expression_path
sed -i "s/sha256 = \".*\";/sha256 = \"$tarball_sha256\";/" $expression_path

nix-build -A gitAndTools.git-machete
nix-env -f . -iA gitAndTools.git-machete
installed_version=$(git machete --version)
[[ ${installed_version/git-machete version /} = $VERSION ]]

branch=git-machete-$VERSION
git checkout -b $branch
git add $expression_path
title="gitAndTools.git-machete: $existing_version -> $VERSION"
message=$(echo "$title"; echo; cat /root/pr-description.md)
git config user.email "travis@travis-ci.com"
git config user.name "Travis CI"
git commit -m "$message"
git push VirtusLab $branch
# 'hub pull-request' relies on GITHUB_TOKEN env var (not on the git remote's URL as 'git push' does) for authentication.
hub pull-request \
  --base NixOS:master \
  --head VirtusLab:$branch \
  --message "$message" \
  --labels='10.rebuild-darwin: 1-10,10.rebuild-linux: 1-10,11.by: upstream-developer'
# Deliberately not setting `--reviewer`, since it's not strictly needed
# and caused non-trivial issues with access of personal OAuth token to organization-owned repo.
