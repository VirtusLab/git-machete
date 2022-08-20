#!/usr/bin/env bash

set -e -o pipefail -u

if git grep -E '^#!/usr/bin/env python(2)?$' .; then
  echo "Ambiguous python shebang, please declare shebangs that point to python3:  #!/usr/bin/env python3"
  exit 1
fi
