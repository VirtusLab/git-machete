#!/usr/bin/env bash

if git grep -n '``' -- '*.py' ':!docs/generate_py_docs.py'; then
  echo
  echo 'Formatting provided by git_machete.utils.fmt only accepts single backticks (`...`).'
  echo 'Double backticks (``...``) are probably a copy-paste from .rst files.'
  exit 1
fi
