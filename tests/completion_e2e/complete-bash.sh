#!/usr/bin/env bash

set -e -o pipefail -u

eval "$(git machete completion bash)"

if ! declare -f __git_complete &>/dev/null; then
  # __git_complete (defined in https://github.com/git/git/blob/master/contrib/completion/git-completion.bash#L3496-L3505)
  # is not public and is loaded by bash_completion dynamically on demand.
  # The solution is to source git completions (from one of these common locations).
  if [ -e /usr/share/bash-completion/completions/git ]; then
    source /usr/share/bash-completion/completions/git
  elif [ -f /usr/local/share/bash-completion/completions/git ]; then
    source /usr/local/share/bash-completion/completions/git
  elif [ -e /etc/bash_completion.d/git ]; then
    source /etc/bash_completion.d/git
  elif [ -e "$(brew --prefix)/etc/bash_completion.d/git-completion.bash" ]; then
    source "$(brew --prefix)/etc/bash_completion.d/git-completion.bash"
  else
    exit 1
  fi
fi

input="$1"
if [[ $input == *" " ]]; then
  input="$input%"
fi
read -r -a COMP_WORDS <<< "$input"
COMPREPLY=()
COMP_CWORD=${#COMP_WORDS[@]}
COMP_CWORD=$((COMP_CWORD-1))
if [[ ${COMP_WORDS[$COMP_CWORD]} == "%" ]]; then
  COMP_WORDS[$COMP_CWORD]=""
fi

_git_machete

echo "${COMPREPLY[*]}" | sed 's/= / /g;  s/=$//'
