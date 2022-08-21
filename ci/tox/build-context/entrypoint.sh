#!/usr/bin/env bash

set -e -o pipefail -u

if [[ ${GID-} && ${UID-} ]]; then
  if ! getent group "$GID" &>/dev/null; then
    addgroup --gid="$GID" docker
  fi
  # `adduser` doesn't accept a numeric GID, we need to extract & provide group name
  # (might not be `docker` if the group existed already in the image).
  group_name=$(getent group "$GID" | cut -d: -f1)
  adduser --disabled-password --ingroup="$group_name" --uid="$UID" docker

  sudo --preserve-env --set-home --user=docker bash -c "$*"
else
  bash -c "$@"
fi
