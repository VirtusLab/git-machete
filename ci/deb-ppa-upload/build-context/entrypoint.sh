#!/usr/bin/env bash

{ [[ -f setup.py ]] && grep -q "name='git-machete'" setup.py; } || {
  echo "Error: the repository should be mounted as a volume under $(pwd)"
  exit 1
}

set -e -o pipefail -u
echo "$GPG_PRIVATE_KEY_PASSPHRASE" > ~/.gnupg/passphrase.txt
echo "$GPG_PRIVATE_KEY_CONTENTS_BASE64" | base64 -d > ~/.gnupg/private-keys-v1.d/"$GPG_PRIVATE_KEY_ID".key
echo "$GPG_PUBRING_KEYBOX_CONTENTS_BASE64" | base64 -d > ~/.gnupg/pubring.kbx
echo "$GPG_TRUSTDB_GPG_CONTENTS_BASE64" | base64 -d > ~/.gnupg/trustdb.gpg
echo "$SSH_PRIVATE_KEY_CONTENTS_BASE64" | base64 -d > ~/.ssh/id_rsa
chmod 400 ~/.ssh/id_rsa

set -x
VERSION=$(python3 setup.py --version)
export VERSION
envsubst '$VERSION' < debian/files.envsubst > debian/files
cp LICENSE debian/copyright
# The first version ever released to PPA is 2.12.8, so we skip everything older than that from the changelog.
sed '/## New in git-machete 2\.12\.7/,$d' RELEASE_NOTES.md | awk \
  -v distro_name="$TARGET_DISTRO_NAME" \
  -v distro_number="$TARGET_DISTRO_NUMBER" \
  -f ~/release-notes-to-changelog.awk > debian/changelog

# Since we upload over SFTP, we need to whitelist the host first to avoid the prompt.
# Let's retry ssh-keyscan to protect again rare spurious failures.
attempts=3
i=1
while true; do
  if ssh-keyscan ppa.launchpad.net > ~/.ssh/known_hosts; then
    break
  elif (( i < attempts )); then
    echo "Retrying ssh-keyscan..."
    i=$((i + 1))
    sleep 5
  else
    echo "ssh-keyscan did not succeed despite $attempts attempts"
    exit 1
  fi
done

# `-p` flag points to a script that wraps gpg so that we don't get asked for password to the private key on TTY.
debuild -S -p"$HOME/gpg-sign.sh"
cat ../python3-git-machete_*.dsc
cat ../python3-git-machete_*_source.buildinfo
cat ../python3-git-machete_*_source.changes
tar tvf ../python3-git-machete_*.tar.gz

if [[ $DO_DPUT == true ]]; then
  dput ppa:virtuslab/git-machete ../python3-git-machete_*_source.changes
else
  echo "Refraining from running 'dput' since it's a dry run"
fi
