#!/usr/bin/env bash

git clone https://github.com/PawelLipski/git-machete.git --depth=1 || { echo >&2 "\`git clone' failed with $?"; exit 1; }
cd git-machete
make install || { echo >&2 "\`make install' failed with $?"; exit 1; }
cd ..
rm -rf git-machete

