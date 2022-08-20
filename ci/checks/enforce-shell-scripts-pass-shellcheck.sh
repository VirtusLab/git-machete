#!/usr/bin/env bash

set -e -o pipefail -u

git ls-files '*.sh' | xargs shellcheck --check-sourced --exclude=SC2090,SC2125,SC1090 --severity=warning --shell=bash
