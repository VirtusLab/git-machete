#!/usr/bin/env bash

set -e -o pipefail -u -x

# `--use-lxd` applied to use a LXD container instead of a VM, to work around lack of support for KVM on CircleCI VMs.

sudo apt-get update
sudo apt-get install -y snapd
sudo snap install snapcraft --classic
sudo lxd init --minimal
snapcraft --use-lxd

! command -v git-machete
sudo snap install git-machete_*.snap --dangerous --classic
git machete version
sudo snap remove git-machete
