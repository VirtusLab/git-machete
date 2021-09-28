#!/usr/bin/env bash

set -e -o pipefail -u

if grep -r -e '^#!\/usr\/bin\/env python$' -e '^#!\/usr\/bin\/env python2$' ../../git_machete; then
  echo "Ambigous python shebang"
  exit 1
fi
