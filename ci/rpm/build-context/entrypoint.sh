#!/usr/bin/env bash

set -e -o pipefail -u

if [[ ${GID-} && ${UID-} ]]; then
  if ! getent group "$GID" &>/dev/null; then
    groupadd --gid="$GID" docker
  fi
  useradd --create-home --gid="$GID" --no-log-init --uid="$UID" docker
  sudo --preserve-env --set-home --user=docker bash -c "$*"
else
  bash -c "$@"
fi
