#!/usr/bin/env bash

set -e -o pipefail -u

if ! ( [ -f setup.py ] && grep -q "name='git-machete'" setup.py ); then
  echo "Error: the repository should be mounted as a volume under $(pwd)"
  exit 1
fi

env | sort | head -4

set -x

if [[ $CHECK_COVERAGE = true ]]; then
  TOX_ENV_LIST="mypy-py${PYTHON_VERSION/./},coverage"
else
  TOX_ENV_LIST="mypy-py${PYTHON_VERSION/./},py${PYTHON_VERSION/./}"
fi

if [[ $BUILD_SPHINX_HTML = true ]]; then
  TOX_ENV_LIST="$TOX_ENV_LIST,sphinx-html"
fi

if [[ $CHECK_DOCS_UP_TO_DATE = true ]]; then
  TOX_ENV_LIST="$TOX_ENV_LIST,py-docs-check,sphinx-man-check"
fi

if [[ $CHECK_PEP8 = true ]]; then
  TOX_ENV_LIST="$TOX_ENV_LIST,pep8-check,isort-check"
fi

tox -e "$TOX_ENV_LIST"

$PYTHON setup.py install --user
PATH=$PATH:$HOME/.local/bin/
git machete --version
