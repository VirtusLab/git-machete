#!/usr/bin/env bash
set -e -o pipefail

# GIT_REVISION: Tag (e.g. 3.38.1) or Hash (e.g. 874931f)
# EXPRESSION_PATH: pkgs/by-name/gi/git-machete/package.nix

echo "--- Cloning nixpkgs ---"
git clone --depth=1 https://github.com/NixOS/nixpkgs.git .

echo "--- Pre-patching expression ---"

# 1. Support raw revisions (tags or hashes) in the fetcher
sed -i 's/tag = "v\${version}"/rev = version/' "$EXPRESSION_PATH"

# 2. Fix the changelog URL
# We replace the broken ${src.tag} with v${version}
# (Most GitHub releases use the 'v' prefix in the URL even if the revision is a hash/tag)
sed -i 's/\${src.tag}/v\${version}/' "$EXPRESSION_PATH"

echo "--- Updating $EXPRESSION_PATH to $GIT_REVISION ---"
# nix-update will now set 'version' and 'hash' correctly.
nix-update git-machete --version "$GIT_REVISION" --build

echo "--- Build and Tests Successful! ---"
cat "$EXPRESSION_PATH"
