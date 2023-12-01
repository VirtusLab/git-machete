## Build & uploading the package to PPA from the local machine

```shell script
cd ci/deb-ppa-upload/
. export-gpg-ssh-config
./local-run.sh
```

## Regenerate GPG keys

```shell
gpg --default-new-key-algo rsa4096 --gen-key
# ECC doesn't seem to be fully supported by Launchpad as of early 2023,
# see https://bugs.launchpad.net/launchpad/+bug/2002884.
# Non-expiring, username `Pawel Lipski`, email `plipski@virtuslab.com`.
# Specify a password, add the password to password manager and CI (GPG_PRIVATE_KEY_PASSPHRASE env var).

gpg --armor --export-secret-key <key-id> | pbcopy
# Add to password manager (directly) & CI (base64-encoded, GPG_PRIVATE_KEY_CONTENTS_BASE64 env var).

gpg --send-keys --keyserver keyserver.ubuntu.com <key-id>
# Check if the key has been uploaded correctly via https://keyserver.ubuntu.com/.

# Then remove the old & add the new GPG key at https://launchpad.net/~virtuslab/+editpgpkeys, logging via admin@virtuslab.com account.
```
