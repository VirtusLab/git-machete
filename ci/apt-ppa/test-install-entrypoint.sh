#!/usr/bin/env bash

set -e -x

apt-get update
apt-get install -y python3-git-machete
git machete --version
apt-get purge -y python3-git-machete
! command -v git-machete
