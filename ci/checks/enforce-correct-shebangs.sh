#!/usr/bin/env bash

set -e -o pipefail -u

if grep -r -e '^#!/usr/bin/env python$' -e '^#!/usr/bin/env python2$' git_machete; then
  echo "Ambigouos python shebang, please declare shebangs that point to python3:  #!/usr/bin/env python3"
  exit 1
fi
