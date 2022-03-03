#!/usr/bin/env bash

set -e -o pipefail -u -x

sudo apt-get update
sudo apt-get install -y snapd
sudo snap install snapcraft --classic
#sudo lxd init --minimal
## `--use-lxd` applied to use a LXD container instead of a VM, to work around lack of support for KVM on CircleCI VMs.
#snapcraft --use-lxd

if [[ ${1-} == "--dry-run" || ${CIRCLE_BRANCH-} != "master" ]]; then
#  ! command -v git-machete
#  sudo snap install git-machete_*.snap --dangerous --classic
#  git machete version
#  sudo snap remove git-machete
  echo "MASTER"
  echo "$SNAPCRAFT_LOGIN_CREDENTIALS_CONTENTS_BASE64" | base64 -d > ~/.snapcraft.login
  snapcraft login --with ~/.snapcraft.login
  snapcraft status test-offlineimap-amalota
else
  echo "MASTER"
  echo "$SNAPCRAFT_LOGIN_CREDENTIALS_CONTENTS_BASE64" | base64 -d > ~/.snapcraft.login
  snapcraft login --with ~/.snapcraft.login
#  snapcraft upload --release=stable *.snap
fi
