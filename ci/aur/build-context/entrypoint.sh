#!/usr/bin/env bash

set -e -o pipefail -u

git clone https://aur.archlinux.org/git-machete.git
cd git-machete

sed -i "s/pkgver=.*/pkgver=${GIT_REVISION}/" PKGBUILD
url=https://github.com/VirtusLab/git-machete/archive/${GIT_REVISION}.tar.gz
sed -i "s!::[^\"]*!::$url!" PKGBUILD

# Refresh package database (to avoid 404s with stale Docker images) and
# install pacman-contrib for `updpkgsums` (used further below).
sudo pacman --sync --refresh --needed --noconfirm pacman-contrib

# Regenerate setup_packages.patch against our current setup.py.
#
# The patch shipped with the AUR PKGBUILD strips 'completion' and 'docs/man'
# from the `packages=[...]` list in setup.py, because the AUR `package()`
# function installs those directories manually via `install -Dm644` and
# doesn't want bdist_wheel to include them as well. The patch pins the
# exact line content from a previous release, so any time we add a new
# entry to packages= (e.g., `git_machete/utils` in 216afaa) the upstream
# patch's hunk fails to apply and the dry-run AUR build breaks until the
# AUR maintainer refreshes the patch.
#
# The transformation is mechanical and safe to reproduce here: derive the
# patch from the current upstream setup.py so the dry-run keeps catching
# real regressions in the rest of the AUR pipeline (build, install, test)
# without being held hostage by every cosmetic change to the packages= list.
setup_py_url=https://raw.githubusercontent.com/VirtusLab/git-machete/${GIT_REVISION}/setup.py
curl -fsSL "$setup_py_url" > /tmp/setup.py.before
cp /tmp/setup.py.before /tmp/setup.py.after
# Idempotent: a no-op once the upstream patch is refreshed and these
# entries are absent from setup.py.
sed -i -E "s/, *'completion'//; s/, *'docs\/man'//" /tmp/setup.py.after
# `diff -u` exits 1 when the files differ - which is the expected, success
# case here. Treat exit 0 / 1 as success, anything else as a real failure.
diff_status=0
diff -u \
  --label package.orig/setup.py \
  --label package.new/setup.py \
  /tmp/setup.py.before /tmp/setup.py.after > setup_packages.patch || diff_status=$?
if [ "$diff_status" -gt 1 ]; then
  echo "diff -u for setup_packages.patch failed unexpectedly (exit ${diff_status})" >&2
  exit 1
fi
rm /tmp/setup.py.before /tmp/setup.py.after
echo '--- regenerated setup_packages.patch ---'
cat setup_packages.patch

# Recompute every `sha256sums=(...)` entry against the current source files
# (the GIT_REVISION tarball + our just-regenerated patch). Without this,
# `makepkg`'s "Validating source files with sha256sums" step rejects the
# patch because its hash in PKGBUILD still pins the AUR-shipped content.
updpkgsums
cat PKGBUILD

makepkg --syncdeps --log --install --clean --noconfirm
