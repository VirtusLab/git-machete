#!/usr/bin/env bash

set -e -o pipefail -u

# xargs for stripping the leading spaces
y_yes_yq_checks=$(git grep 'if ans in.*yq' '*.py' | wc -l | xargs)
yq_checks=$(git grep 'if ans ==.*yq' '*.py' | wc -l | xargs)

if [[ $yq_checks != "$y_yes_yq_checks" ]]; then
  echo "In Python code, the number of checks for 'y', 'yes', 'yq' answers on interactive input ($y_yes_yq_checks)"
  echo "is NOT equal to the number of narrower checks for 'yq' answer ($yq_checks)."
  echo
  echo "Does it mean that 'yq' is treated just as 'y' in some cases (without quitting)?"
  echo "See https://github.com/VirtusLab/git-machete/pull/1421 for a sample fix."
  exit 1
fi
