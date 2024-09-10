#!/usr/bin/env bash

set -e -o pipefail -u

if [[ ${1-} == "--dry-run" || ${CIRCLE_BRANCH-} != "master" ]]; then
  repository=testpypi
  token=$TEST_PYPI_TOKEN
else
  repository=pypi
  token=$PYPI_TOKEN
fi

cat > ~/.pypirc <<EOF
[$repository]
username = __token__
password = $token
EOF

set -x
pip3 install -r requirements/pypi-publish.txt
python3 -m build
python3 -m twine upload --repository $repository --skip-existing dist/*
