#!/usr/bin/env bash

if git grep -EIn ' +$' -- :!git_machete/generated_docs.py; then
  echo 'The above lines contain trailing whitespace, please tidy up'
  exit 1
fi
