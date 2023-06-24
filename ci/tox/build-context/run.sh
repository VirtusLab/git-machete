#!/usr/bin/env bash

set -e -o pipefail -u

if ! ( [ -f setup.py ] && grep -q "name='git-machete'" setup.py ); then
  echo "Error: the repository should be mounted as a volume under $(pwd)"
  exit 1
fi

env | sort | head -4

set -x

TOX_ENV_LIST="mypy,coverage"

if [[ $BUILD_SPHINX_HTML = true ]]; then
  TOX_ENV_LIST="$TOX_ENV_LIST,sphinx-html"
fi

if [[ $CHECK_DOCS_UP_TO_DATE = true ]]; then
  TOX_ENV_LIST="$TOX_ENV_LIST,py-docs-check,sphinx-man-check"
fi

if [[ $CHECK_PEP8 = true ]]; then
  TOX_ENV_LIST="$TOX_ENV_LIST,isort-check,pep8-check,vulture-check"
fi

tox -e "$TOX_ENV_LIST"

$PYTHON setup.py sdist bdist_wheel

tar tvf dist/git-machete-*.tar.gz | grep docs/man/git-machete.1
unzip -v dist/git_machete-*.whl   | grep docs/man/git-machete.1

$PYTHON -m venv venv/sdist/
$PYTHON -m venv venv/bdist_wheel/

. venv/sdist/bin/activate
pip install dist/git-machete-*.tar.gz
git machete version
if ! git machete completion fish | grep 'complete -c git-machete'; then
  echo "shell completion is not available in runtime, aborting"
  exit 1
fi

. venv/bdist_wheel/bin/activate
pip install dist/git_machete-*.whl
git machete version
if ! git machete completion zsh | grep '#compdef git-machete'; then
  echo "shell completion is not available in runtime, aborting"
  exit 1
fi
