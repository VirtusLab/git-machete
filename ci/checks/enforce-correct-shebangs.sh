#!/usr/bin/env bash

set -e -o pipefail -u

find ../../git_machete -type f -name "*.py" -exec sed -i '' 's/#!\/usr\/bin\/env python$/#!\/usr\/bin\/env python3/g;s/#!\/usr\/bin\/env python2$/#!\/usr\/bin\/env python3/g' {} \;