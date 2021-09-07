#!/bin/sh

{ [ -f setup.py ] && grep -q "name='git-machete'" setup.py; } || {
  echo "Error: the repository should be mounted as a volume under $(pwd)"
  exit 1
}

set -e -u -x

if [[ $CHECK_COVERAGE = true ]]; then
  TOX_ENV_LIST="pep8,coverage"
else
  TOX_ENV_LIST="pep8,py${PYTHON_VERSION/./}"
fi

if [[ $BUILD_DOCS = true ]]; then
  TOX_ENV_LIST="$TOX_ENV_LIST,docs"
fi

tox -e $TOX_ENV_LIST

$PYTHON setup.py install --user
git machete --version
