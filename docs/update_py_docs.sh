#!/usr/bin/env bash

set -e -o pipefail -u

python docs/generate_py_docs.py > git_machete/docs.py