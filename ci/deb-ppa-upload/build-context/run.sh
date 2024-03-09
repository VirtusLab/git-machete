#!/usr/bin/env bash

set -e -o pipefail -u

if ! ( [ -f setup.py ] && grep -q "name='git-machete'" setup.py ); then
  echo "Error: the repository should be mounted as a volume under $(pwd)"
  exit 1
fi

install -d -m 0700 ~/.gnupg/ ~/.gnupg/private-keys-v1.d/ ~/.ssh/
echo "$GPG_PRIVATE_KEY_PASSPHRASE" > ~/.gnupg/passphrase.txt
echo "$GPG_PRIVATE_KEY_CONTENTS_BASE64" | base64 -d > ~/.gnupg/private.key
/gpg-wrapper.sh --import ~/.gnupg/private.key
echo "$SSH_PRIVATE_KEY_CONTENTS_BASE64" | base64 -d > ~/.ssh/id_rsa
chmod 400 ~/.ssh/id_rsa

set -x
VERSION=$(cut -d\' -f2 git_machete/__init__.py)
export VERSION
envsubst '$VERSION' < debian/files.envsubst > debian/files
cp LICENSE debian/copyright
# The first version ever released to PPA is 2.12.8, so we skip everything older than that from the changelog.
sed '/## New in git-machete 2\.12\.7/,$d' RELEASE_NOTES.md | awk \
  -v distro_name="$TARGET_DISTRO_NAME" \
  -v distro_number="$TARGET_DISTRO_NUMBER" \
  -v gpg_email="$GPG_EMAIL" \
  -v gpg_username="$GPG_USERNAME" \
  -f /release-notes-to-changelog.awk > debian/changelog

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
debuild -S -p"/gpg-wrapper.sh"
cat ../python3-git-machete_*.dsc
cat ../python3-git-machete_*_source.buildinfo
cat ../python3-git-machete_*_source.changes

tar_output=$(tar tvf ../python3-git-machete_*.tar.gz)
echo "$tar_output"
grep completion/ <<< "$tar_output"
grep docs/man/git-machete\.1 <<< "$tar_output"

envsubst '$LAUNCHPAD_USERNAME' < /dput.cf.envsubst | tee /etc/dput.cf
if [[ $DO_DPUT == true ]]; then
  dput ppa:virtuslab/git-machete ../python3-git-machete_*_source.changes
else
  echo "Refraining from running 'dput' since it's a dry run"
fi
