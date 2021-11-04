#!/usr/bin/env bash

set -e -o pipefail -u

bash completion/git-machete.completion.bash
zsh  completion/git-machete.completion.zsh
fish completion/git-machete.fish
