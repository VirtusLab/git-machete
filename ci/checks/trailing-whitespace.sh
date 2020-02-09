#!/usr/bin/env bash

git grep -EIn '\s+$' && {
  echo 'The above lines contain trailing whitespace, please tidy up'
  exit 1
} || true
