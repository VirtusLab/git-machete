#!/usr/bin/env bash

set -e -o pipefail -u -x

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

pip3 install twine wheel
python3 setup.py sdist
python3 setup.py bdist_wheel
python3 -m twine upload --repository $repository --skip-existing dist/*
