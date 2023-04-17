#!/usr/bin/env bash

if git grep -n '\[.*\](.*)' -- '*.rst'; then
  echo
  echo 'ReStructuredText uses a different syntax for links than Markdown: not [text](url) but `text <url>`_'
  exit 1
fi
