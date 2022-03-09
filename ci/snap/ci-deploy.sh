#!/usr/bin/env bash

set -e -o pipefail -u

sudo apt-get update
sudo apt-get install -y snapd
sudo snap install review-tools
sudo snap install snapcraft --classic
sudo lxd init --minimal
# `--use-lxd` applied to use a LXD container instead of a VM, to work around lack of support for KVM on CircleCI VMs.
snapcraft --use-lxd

if [[ ${1-} == "--dry-run" || ${CIRCLE_BRANCH-} != "master" ]]; then
  ! command -v git-machete
  sudo snap install git-machete*.snap --dangerous --classic
  git machete version
  sudo snap remove git-machete
else
  echo "$SNAPCRAFT_LOGIN_CREDENTIALS_CONTENTS_BASE64" | base64 -d > ~/.snapcraft.login
  snapcraft login --with ~/.snapcraft.login
  snapcraft upload --release=edge git-machete*.snap #NOTE: TO BE CHANGED FROM edge TO stable
  snapcraft status git-machete
fi
