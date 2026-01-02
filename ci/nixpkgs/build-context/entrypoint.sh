#!/usr/bin/env bash
set -e -o pipefail

# Required Env Vars:
# GIT_REVISION: The version/tag you want to test (e.g., "3.38.1")
# EXPRESSION_PATH: Path inside nixpkgs (e.g., "pkgs/by-name/gi/git-machete/package.nix")

echo "--- Cloning nixpkgs ---"
git clone --depth=1 https://github.com/NixOS/nixpkgs.git .

echo "--- Updating $EXPRESSION_PATH to version $GIT_REVISION ---"
# nix-update will:
# 1. Modify the version string in the .nix file
# 2. Fetch the source for that version
# 3. Calculate the correct hash
# 4. Replace the old hash in the .nix file
# 5. Run the build to verify everything
nix-update git-machete --version "$GIT_REVISION" --build

echo "--- Build and Tests Successful! ---"
# Show the modified file so you can see the clean update
cat "$EXPRESSION_PATH"
