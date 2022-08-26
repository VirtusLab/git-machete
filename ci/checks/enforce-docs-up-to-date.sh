#!/usr/bin/env bash

pip install bs4
pip install docutils
pip install pygments
pip install ../../

pwd
previous_pwd=$(pwd)
cd ../../

current_docs=$(cat git_machete/docs.py)
generated_docs=$(python docs/generate_docs.py)
if [[ $current_docs != "$generated_docs" ]]; then
  cd $previous_pwd || return
  exit 1
fi

cd $previous_pwd || return
