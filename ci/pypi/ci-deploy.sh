#!/usr/bin/env bash

set -e -o pipefail -u

if [[ ${1-} == "--dry-run" || ${CIRCLE_BRANCH-} != "master" ]]; then
  repository=testpypi
  token=$TEST_PYPI_TOKEN
  set -x
  current_version=$(cut -d\' -f2 git_machete/__init__.py)
  latest_pypi_version=$(curl -s "https://test.pypi.org/pypi/git-machete/json" | jq -r '.releases | keys | .[]' | sort -V | tail -1)
  if [[ ${latest_pypi_version} == "$current_version".post* ]]; then
    ordinal=${latest_pypi_version#*.post}
    ordinal=$((ordinal+1))
  else
    ordinal=1
  fi
  sed -i "s/'$/-$ordinal'/" git_machete/__init__.py
  cat git_machete/__init__.py
  set +x
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
python3 -m twine upload --repository $repository --skip-existing --verbose dist/*
