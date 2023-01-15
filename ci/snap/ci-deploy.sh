#!/usr/bin/env bash

set -e -o pipefail -u -x

# By default, CircleCi VM's terminal width and height equals 0 which causes `craft_cli/messages.py`, line 279 to exit with `ZeroDivisionError`.
# The terminal width in `craft_cli/messages.py` is being retrieved by `shutil.get_terminal_size()` using `COLUMNS` env var on line 1365
# from `https://github.com/python/cpython/blob/3.10/Lib/shutil.py`, which can be easily fixed by setting `COLUMNS` env var value to some positive number.
# Reference to the issue: https://github.com/canonical/craft-cli/issues/85
export COLUMNS=1

sudo apt-get update
sudo apt-get install -y snapd
sudo snap install review-tools
sudo snap install snapcraft --classic

sudo snap install lxd
sudo lxd init --minimal
# Workaround taken from https://discuss.linuxcontainers.org/t/lxdbr0-firewall-problem-with-ubuntu-22-04-host-running-docker-and-lxd/15298
sudo iptables -A FORWARD -i lxdbr0 -j ACCEPT
sudo iptables -A FORWARD -o lxdbr0 -j ACCEPT
# `--use-lxd` applied to use a LXD container instead of a VM, to work around lack of support for KVM on CircleCI VMs.
snapcraft --use-lxd

if [[ ${1-} == "--dry-run" || ${CIRCLE_BRANCH-} != "master" ]]; then
  if command -v git-machete; then exit 1; fi
  sudo snap install git-machete*.snap --dangerous --classic
  git machete version
  sudo snap remove git-machete
else
  # Relying on SNAPCRAFT_STORE_CREDENTIALS, provided by the CI
  snapcraft upload --release=stable git-machete*.snap
  snapcraft status git-machete
fi
