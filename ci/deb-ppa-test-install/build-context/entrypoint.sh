#!/usr/bin/env bash

set -e -o pipefail -u -x

apt-get update
apt-get install --no-install-recommends -y python3-git-machete
git machete --version
apt-get autoremove --purge -y python3-git-machete
! command -v git-machete
