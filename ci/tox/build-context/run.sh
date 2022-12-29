#!/usr/bin/env bash

set -e -o pipefail -u

if ! ( [ -f setup.py ] && grep -q "name='git-machete'" setup.py ); then
  echo "Error: the repository should be mounted as a volume under $(pwd)"
  exit 1
fi

env | sort | head -3

set -x

if [[ $CHECK_COVERAGE = true ]]; then
  TOX_ENV_LIST="mypy-py${PYTHON_VERSION/./},coverage"
else
  TOX_ENV_LIST="mypy-py${PYTHON_VERSION/./},py${PYTHON_VERSION/./}"
fi

if [[ $BUILD_SPHINX_DOCS = true ]]; then
  TOX_ENV_LIST="$TOX_ENV_LIST,sphinx-docs"
fi

if [[ $CHECK_PY_DOCS_UP_TO_DATE = true ]]; then
  TOX_ENV_LIST="$TOX_ENV_LIST,check-py-docs"
fi

if [[ $CHECK_PEP8 = true ]]; then
  TOX_ENV_LIST="$TOX_ENV_LIST,pep8,isort-check"
fi

tox -e $TOX_ENV_LIST

$PYTHON setup.py install --user
PATH=$PATH:$HOME/.local/bin/
git machete --version
