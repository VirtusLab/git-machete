#!/usr/bin/env bash

set -e -o pipefail -u

host=$1
timeout_minutes=${2-30}
version=$(python3 setup.py --version)
url=https://$host/packages/source/g/git-machete/git-machete-$version.tar.gz

for i in $(seq 1 "$timeout_minutes"); do
  echo "Checking package availability at $url, attempt #$i out of $timeout_minutes..."
  if curl --fail --location --silent --show-error --output /dev/null "$url"; then
    echo "Package available at $url"
    exit 0
  fi
  sleep 60
done

echo "Package still not published after $timeout_minutes attempts"
exit 1
