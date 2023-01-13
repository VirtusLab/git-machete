#!/usr/bin/env bash

set -e -o pipefail -u

git ls-files '*.sh' | xargs shellcheck --check-sourced --exclude=SC1090,SC1091,SC2016,SC2086,SC2090,SC2125 --severity=info --shell=bash
