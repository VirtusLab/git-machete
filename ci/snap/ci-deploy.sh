#!/usr/bin/env bash

set -e -o pipefail -u

sudo apt-get update
sudo apt-get install -y snapd
#sudo snap install review-tools
#sudo apt-get install --reinstall resolvconf
sudo snap install multipass --classic
sudo snap restart multipass.multipassd
#sudo chmod a+w /var/snap/multipass/common/multipass_socket
sudo snap install snapcraft --edge --classic
#sudo lxd init --minimal
# `--use-lxd` applied to use a LXD container instead of a VM, to work around lack of support for KVM on CircleCI VMs.
#snapcraft --use-lxd
snapcraft
#docker run -v $(pwd):$(pwd) -t ubuntu:xenial sh -c "apt update -qq && apt install snapcraft -y && cd $(pwd) && snapcraft"

if [[ ${1-} == "--dry-run" || ${CIRCLE_BRANCH-} != "master" ]]; then
#  ! command -v git-machete
#  sudo snap install git-machete*.snap --dangerous --classic
#  git machete version
#  sudo snap remove git-machete
  echo "MASTER"
  echo "$SNAPCRAFT_LOGIN_CREDENTIALS_CONTENTS_BASE64" base64 -d > ~/.snapcraft.login
  snapcraft login --with ~/.snapcraft.login
#  snapcraft register git-machete3 --yes
  snapcraft push git-machete*.snap
  snapcraft upload --release=edge git-machete*.snap
  snapcraft status git-machete3
else
  echo "MASTER"
  echo "$SNAPCRAFT_LOGIN_CREDENTIALS_CONTENTS_BASE64" | base64 -d > ~/.snapcraft.login
  snapcraft login --with ~/.snapcraft.login
  snapcraft upload --release=stable git-machete*.snap
fi
