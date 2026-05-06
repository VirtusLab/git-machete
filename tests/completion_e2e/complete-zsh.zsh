#!/usr/bin/env zsh

set -e -o pipefail -u

# Adapted from https://unix.stackexchange.com/a/668827

comptest () {
  eval "$(git machete completion zsh)"

  # Gather all matching completions in this array.
  # -U discards duplicates.
  typeset -aU completions=()

  # Override the builtin compadd command.
  compadd () {
    # Gather all matching completions for this call in $reply.
    # Note that this call overwrites the specified array.
    # Therefore we cannot use $completions directly.
    builtin compadd -O reply "$@"

    completions+=("$reply[@]") # Collect them.
    builtin compadd "$@"       # Run the actual command.
  }

  # Bind a custom widget to TAB.
  bindkey "^I" complete-word
  zle -C {,,}complete-word
  complete-word () {
    # Make the completion system believe we're on a normal
    # command line, not in vared.
    unset 'compstate[vared]'

    _main_complete "$@"  # Generate completions.

    # Print out our completions.
    # Use of ^B and ^C as delimiters here is arbitrary.
    # Just use something that won't normally be printed.
    print -n $'\C-B'
    print -nlr -- "$completions[@]"  # Print one per line.
    print -n $'\C-C'
    exit
  }

  vared -c tmp
}

_run_once () {
  local input=$1 preamble="" accumulated="" chunk="" i

  # Create a new pty and run our function in it.
  zpty {,}comptest

  # Wait for vared to produce any output, which means it has started up and
  # switched the terminal to raw mode.  On macOS we must NOT send any input
  # before that moment: the pty's cooked-mode line discipline would process
  # the TAB before ZLE sees it (expanding it or echoing it away) and the
  # completion widget would never fire.
  for i in $(seq 1 100); do
    if zpty -r -t comptest chunk 2>/dev/null; then
      preamble+="$chunk"
      break
    fi
    sleep 0.05
  done

  if [[ -z "$preamble" ]]; then
    zpty -d comptest 2>/dev/null
    return 1
  fi

  # Now in raw mode: send the input text followed by TAB to trigger the widget.
  zpty -w comptest "$input"$'\t'

  # Accumulate output until we see ^C (the completion widget's final marker).
  # We poll with non-blocking reads because on macOS zpty -r with a pattern
  # blocks forever when the pattern is never matched, even after pty exits.
  for i in $(seq 1 80); do
    if zpty -r -t comptest chunk 2>/dev/null; then
      accumulated+="$chunk"
      [[ "$accumulated" == *$'\C-C'* ]] && break
    else
      sleep 0.05
    fi
  done

  zpty -d comptest 2>/dev/null

  [[ "$accumulated" == *$'\C-C'* ]] || return 1

  local result="${accumulated#*$'\C-B'}"
  echo "${result%$'\C-C'*}"
}

autoload -Uz compinit && compinit
# Load the pseudo terminal module.
zmodload zsh/zpty

input=$1

# Retry up to 5 times.  On macOS the ZLE widget occasionally fails to fire on
# the first attempt due to a timing race in the pty subprocess; a subsequent
# attempt virtually always succeeds.
local result=""
for _ in $(seq 1 5); do
  result=$(_run_once "$input" 2>/dev/null) && break
  result=""
done

echo "$result"
