#!/usr/bin/env bash

pip install bs4
pip install docutils
pip install pygments
pip install ../../

pwd
previous_pwd=$(pwd)
cd ../../docs || return
python generate_docs.py
cd $previous_pwd || return
