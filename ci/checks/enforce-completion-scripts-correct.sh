#!/usr/bin/env bash

set -e -o pipefail -u

bash completion/git-machete.completion.bash >/dev/null
zsh  completion/git-machete.completion.zsh  >/dev/null
fish completion/git-machete.fish            >/dev/null
