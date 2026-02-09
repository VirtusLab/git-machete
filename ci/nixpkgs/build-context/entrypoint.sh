#!/usr/bin/env bash
set -e -o pipefail -u -x

# GIT_REVISION: tag (e.g. v3.38.1) or hash (e.g. 874931f)

EXPRESSION_PATH=pkgs/by-name/gi/git-machete/package.nix

git clone --depth=1 https://github.com/NixOS/nixpkgs.git .

sed -i 's/tag = "v\${.*version}"/rev = finalAttrs.version/' "$EXPRESSION_PATH"

# Remove changelog URL as it contains ${src.tag} which is undefined after the sed above
sed -i '/changelog = / d' "$EXPRESSION_PATH"

# Disable postInstallCheck when testing with commit hashes
# The postInstallCheck expects the version output to match the nix package version,
# but when we're testing a commit hash, the actual version in the code won't match.
sed -i '/postInstallCheck = /, /'';$/ d' "$EXPRESSION_PATH"

git diff "$EXPRESSION_PATH" | cat

# nix-update will now set 'version' and 'hash' correctly, and also run the tests.
nix-update git-machete --version "$GIT_REVISION" --build

cat "$EXPRESSION_PATH"

git diff "$EXPRESSION_PATH" | cat
