#!/usr/bin/env bash

set -e -o pipefail -u -x

git clone --depth=1 https://github.com/NixOS/nixpkgs.git .

source_hash=$(nix-prefetch-url --unpack https://github.com/VirtusLab/git-machete/archive/$GIT_REVISION.tar.gz)
version=$(curl https://raw.githubusercontent.com/VirtusLab/git-machete/$GIT_REVISION/git_machete/__init__.py | cut -d\' -f2)
sed -i -f- $EXPRESSION_PATH <<EOF
  s/version = ".*"/version = "$version"/
  s/rev = \".*\"/rev = \"$GIT_REVISION\"/
  s/sha256 = ".*"/sha256 = "$source_hash"/
  /git init/d
  s/stestr run/pytest/
  s/stestr/pytest/
EOF
cat $EXPRESSION_PATH

nix-build -A gitAndTools.git-machete
