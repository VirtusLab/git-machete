#!/usr/bin/env bash

set -e -o pipefail -u

[[ $(git symbolic-ref --short HEAD) = master ]] || {
    echo "HEAD does not point to master, aborting"
    exit 1
}

[[ $(git rev-parse master) = $(git rev-parse origin/master) ]] || {
    echo "master and origin/master do not point to the same commit, aborting"
    exit 1
}

version=v$(grep '__version__ = ' git_machete/__init__.py | cut -d\' -f2)
git tag -a -F <(echo -ne "$version"'\n\n' && sed '4,/^$/!d; /^$/d' RELEASE_NOTES.md) "$version"
git cat-file -p "$version"
