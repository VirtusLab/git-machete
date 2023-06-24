#!/usr/bin/env fish

git machete completion fish | source

set input "$argv[1]"
complete -C "$input" | cut -f1 | sed -E 's/^--.+=(.+)$/\1/'
