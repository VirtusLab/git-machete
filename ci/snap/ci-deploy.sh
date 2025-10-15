#!/usr/bin/env bash

set -e -o pipefail -u -x

sudo apt-get update
sudo apt-get install -y snapd
sudo snap install snapcraft --classic

sudo snap install lxd
sudo lxd init --minimal
# Workaround taken from https://discuss.linuxcontainers.org/t/lxdbr0-firewall-problem-with-ubuntu-22-04-host-running-docker-and-lxd/15298
sudo iptables -A FORWARD -i lxdbr0 -j ACCEPT
sudo iptables -A FORWARD -o lxdbr0 -j ACCEPT
# `--use-lxd` applied to use a LXD container instead of a VM, to work around lack of support for KVM on CircleCI VMs.
snapcraft --use-lxd
ls -l -- *.snap

if [[ ${1-} == "--dry-run" || ${CIRCLE_BRANCH-} != "master" ]]; then
  if command -v git-machete; then exit 1; fi
  sudo snap install git-machete_*_amd64.snap --dangerous --classic
  git machete version
  if ! git machete completion bash | grep '#!.*bash'; then
    echo "shell completion is not available in runtime, aborting"
    exit 1
  fi
  sudo snap remove git-machete

  snapcraft upload --release=edge git-machete_*_amd64.snap
  snapcraft upload --release=edge git-machete_*_arm64.snap
else
  # Relying on SNAPCRAFT_STORE_CREDENTIALS, provided by the CI
  snapcraft upload --release=stable git-machete_*_amd64.snap
  snapcraft upload --release=stable git-machete_*_arm64.snap
  snapcraft status git-machete
fi
