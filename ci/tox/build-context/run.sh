#!/usr/bin/env bash

set -e -o pipefail -u

if ! ( [ -f setup.py ] && grep -q "name='git-machete'" setup.py ); then
  echo "Error: the repository should be mounted as a volume under $(pwd)"
  exit 1
fi

env | sort | head -4

set -x

tox -e mypy,coverage

$PYTHON setup.py sdist bdist_wheel

ls -l dist/
# Name of the generated tar.gz changed in a certain setuptools/Python version from git-machete-... to git_machete-...,
# let's cater for both variants
tar tvf dist/git*machete-*.tar.gz | grep docs/man/git-machete.1
unzip -v dist/git_machete-*.whl   | grep docs/man/git-machete.1

$PYTHON -m venv venv/sdist/
$PYTHON -m venv venv/bdist_wheel/

. venv/sdist/bin/activate
pip install dist/git*machete-*.tar.gz
git machete version
if ! git machete completion fish | grep 'complete -c git-machete'; then
  echo "fish completion is not available in runtime, aborting"
  exit 1
fi

. venv/bdist_wheel/bin/activate
pip install dist/git_machete-*.whl
git machete version
if ! git machete completion zsh | grep '#compdef git-machete'; then
  echo "zsh completion is not available in runtime, aborting"
  exit 1
fi
