#!/usr/bin/env bash

if git grep -EIn '\s+$' -- :!'*.py'; then
  echo 'The above lines contain trailing whitespace, please tidy up'
  exit 1
fi
