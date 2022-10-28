#!/usr/bin/env bash

set -e -o pipefail -u

# By default, CircleCi VM's terminal width and height equals 0 which causes `craft_cli/messages.py`, line 279 to exit with `ZeroDivisionError`.
# The terminal width in `craft_cli/messages.py` is being retrieved by `shutil.get_terminal_size()` using `COLUMNS` env var on line 1365
# from `https://github.com/python/cpython/blob/3.10/Lib/shutil.py`, which can be easily fixed by setting `COLUMNS` env var value to some positive number.
# Reference to the issue: https://github.com/canonical/craft-cli/issues/85
export COLUMNS=1

sudo apt-get update
sudo apt-get install -y snapd
sudo snap install review-tools
sudo snap install snapcraft --classic
sudo lxd init --minimal
# `--use-lxd` applied to use a LXD container instead of a VM, to work around lack of support for KVM on CircleCI VMs.
snapcraft --use-lxd

if [[ ${1-} == "--dry-run" ]]; then
  ! command -v git-machete
  sudo snap install git-machete*.snap --dangerous --classic
  git machete version
  sudo snap remove git-machete
else
#  echo "$SNAPCRAFT_LOGIN_CREDENTIALS_CONTENTS_BASE64" | base64 -d > ~/.snapcraft.login
#  cat /home/circleci/.cache/snapcraft/log/snapcraft-20220708-133250.692570.log
  export SNAPCRAFT_STORE_CREDENTIALS=$SNAPCRAFT_LOGIN_CREDENTIALS_CONTENTS_BASE64
  snapcraft login
  snapcraft whoami
  snapcraft upload --release=edge git-machete*.snap
  snapcraft status git-machete
fi
