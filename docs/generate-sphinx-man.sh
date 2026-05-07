#!/usr/bin/env bash

set -e -o pipefail -u

target_dir=$1

# `-t man` is needed for the conditionally rendered sections
sphinx-build -W --keep-going -b man -t man docs/source "$target_dir"

# Strip the date from the .TH header so the generated file is deterministic
# (the date is irrelevant for `man` display and changes on every regeneration).
sed -i.bak 's/^\(\.TH "GIT-MACHETE" "1"\) "[^"]*"/\1 ""/' "$target_dir/git-machete.1"
rm -f "$target_dir/git-machete.1.bak"
