#!/bin/sh

{ [ -f setup.py ] && grep -q "name='git-machete'" setup.py; } || {
  echo "Error: the repository should be mounted as a volume under $(pwd)"
  exit 1
}

set -e -u -x

env | sort | head -3

if [[ $CHECK_COVERAGE = true ]]; then
  TOX_ENV_LIST="mypy-py${PYTHON_VERSION/./},coverage"
else
  TOX_ENV_LIST="mypy-py${PYTHON_VERSION/./},py${PYTHON_VERSION/./}"
fi

if [[ $BUILD_DOCS = true ]]; then
  TOX_ENV_LIST="$TOX_ENV_LIST,docs"
fi

if [[ $CHECK_PEP8 = true ]]; then
  TOX_ENV_LIST="$TOX_ENV_LIST,pep8"
fi

ls -al
tox -e $TOX_ENV_LIST

$PYTHON setup.py install --user
git machete --version
