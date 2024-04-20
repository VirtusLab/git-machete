#!/usr/bin/env bash

set -e -o pipefail -u

host=$1
timeout_minutes=${2-10}
version=$(cut -d\' -f2 git_machete/__init__.py)
url=https://$host/pypi/git-machete/$version/json

# Typically just 2 minutes of waiting are enough.
for i in $(seq 1 "$timeout_minutes"); do
  echo "Checking package availability at $url, attempt #$i out of $timeout_minutes..."
  if curl --fail --location --silent --show-error "$url"; then
    echo "Package metadata available at $url"
    exit 0
  fi
  sleep 60
done

echo "Package still not published after $timeout_minutes minutes"
exit 1
