#!/usr/bin/env bash

set -e -o pipefail -u

git clone https://aur.archlinux.org/git-machete.git
cd git-machete

sed -i "s/pkgver=.*/pkgver=${GIT_REVISION}/" PKGBUILD
url=https://github.com/VirtusLab/git-machete/archive/${GIT_REVISION}.tar.gz
sed -i "s!::[^\"]*!::$url!" PKGBUILD
hash=$(curl -L -s $url | sha256sum | head -c 64)
sed -i "s/sha256sums=('[^']*/sha256sums=('$hash/" PKGBUILD
cat PKGBUILD

makepkg --syncdeps --log --install --clean --noconfirm
