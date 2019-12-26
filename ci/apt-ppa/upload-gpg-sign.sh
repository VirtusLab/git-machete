#!/usr/bin/env bash

# --pinentry-mode=loopback is the only option (--batch, --yes, --passphrase-fd 0 all had no effect) that makes it possible for gpg NOT to ask for password via a TTY within Docker context.
gpg --pinentry-mode=loopback --passphrase-file="$HOME/.gnupg/passphrase.txt" "$@"
