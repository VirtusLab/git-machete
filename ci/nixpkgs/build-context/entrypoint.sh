#!/usr/bin/env bash
set -e -o pipefail

# GIT_REVISION: Can be a tag (3.38.1) or a hash (874931f...)
# EXPRESSION_PATH: pkgs/by-name/gi/git-machete/package.nix

echo "--- Cloning nixpkgs ---"
git clone --depth=1 https://github.com/NixOS/nixpkgs.git .

echo "--- Pre-patching expression to support raw revisions ---"
# We change 'tag = "v${version}"' to 'rev = version'
# This makes the expression compatible with both version numbers and commit hashes.
sed -i.bak 's/tag = "v\${version}"/rev = version/' "$EXPRESSION_PATH"

echo "--- Updating $EXPRESSION_PATH to $GIT_REVISION ---"
# --version will now set the 'version' variable to your hash/tag.
# Since we changed the .nix file to use 'rev = version',
# the URL will now correctly point to the raw revision.
nix-update git-machete --version "$GIT_REVISION" --build

echo "--- Build and Tests Successful! ---"
cat "$EXPRESSION_PATH"
