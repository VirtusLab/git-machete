# git-machete

[![Join the chat at https://gitter.im/VirtusLab/git-machete](https://badges.gitter.im/VirtusLab/git-machete.svg)](https://gitter.im/VirtusLab/git-machete)
[![TravisCI build status](https://api.travis-ci.org/VirtusLab/git-machete.svg?branch=master)](https://travis-ci.org/VirtusLab/git-machete)
[![PyPI package](https://badge.fury.io/py/git-machete.svg)](https://pypi.org/project/git-machete)
[![Snap](https://snapcraft.io/git-machete/badge.svg)](https://snapcraft.io/git-machete)
[![Snap build status](https://build.snapcraft.io/badge/VirtusLab/git-machete.svg)](https://build.snapcraft.io/user/VirtusLab/git-machete)

![](logo.png)

**git machete is a versatile tool for organizing your git repo:**

`git machete discover` suggests a layout of branches (which branch is derived/forked off which),

`git machete status` shows whether branches are in sync with their parent branch (via green/red edges) and their remote tracking branch,

`git machete traverse` semi-automatically traverses the branches, helping you effortlessly rebase, merge, push and pull.

[![git machete discover, status & traverse](docs/discover-status-traverse.gif)](docs/discover-status-traverse.gif)


A port to an IntelliJ plugin is under development, see [VirtusLab/git-machete-intellij-plugin](http://github.com/VirtusLab/git-machete-intellij-plugin/).


## Install

We suggest a couple of alternative ways of installation.

**Bash and zsh completion scripts are provided** in completion/ directory, see [wiki for their installation instructions](https://github.com/VirtusLab/git-machete/wiki).

git-machete works under both Python 2.7 and Python 3.x.

### Using Homebrew (macOS)

```shell script
brew tap VirtusLab/git-machete
brew install git-machete
```

### Using Snappy (most Linux distributions)

Tip: check the [guide on installing snapd](https://snapcraft.io/docs/installing-snapd) if you don't have Snap support set up yet in your system.

```shell script
sudo snap install --classic git-machete
```

It can also be installed via Ubuntu Software (simply search for `git-machete`).

Note: classic confinement is necessary to ensure access to the editor installed in the system (to edit e.g. .git/machete file or rebase TODO list).

### Using PPA (Ubuntu)

Tip: run `sudo apt-get install -y software-properties-common` first if `add-apt-repository` is not available on your system.

```shell script
sudo add-apt-repository ppa:virtuslab/git-machete
sudo apt-get update
sudo apt-get install -y python3-git-machete
```

### Using rpm (Fedora/RHEL/CentOS/openSUSE...)

Download the rpm package from the [latest release](https://github.com/VirtusLab/git-machete/releases/latest)
and install either by opening it in your desktop environment or with `rpm -i git-machete-*.noarch.rpm`.

### Using AUR (Arch Linux)

Install the AUR package [git-machete](https://aur.archlinux.org/packages/git-machete) using an AUR helper of your preference.

### Using Nix (macOS & most Linux distributions)

On macOS and most Linux distributions, you can install via [Nix](https://nixos.org/nix):

```shell script
nix-channel --add https://nixos.org/channels/nixos-unstable unstable  # if you haven't set up any channels yet
nix-env -i git-machete
```

### Using pip with sudo (system-wide install)

You need to have Python and `pip` installed from system packages.

```shell script
sudo -H pip install git-machete
```

Tip: pass an extra `-U` flag to `pip install` to upgrade an already installed version.

### Using pip without sudo (user-wide install)

You need to have Python and `pip` installed from system packages.

```shell script
pip install --user git-machete
```

Please verify that your `PATH` variable has `${HOME}/.local/bin/` included.

Tip: pass an extra `-U` flag to `pip install` to upgrade an already installed version.


## Quick start

```shell script
cd your-repo/
git machete discover --checked-out-since='2 weeks ago'  # increase/decrease the timespan if you want more/less old branches included
  # (see and possibly edit the suggested layout of branches - branch layout is always kept as text file .git/machete)
git machete traverse --fetch --start-from=first-root
  # (put each branch one by one in sync with its parent and remote counterpart)
```


## Git compatibility

git-machete (since version 2.13.0) is compatible with git >= 1.7.10.


## Reference

See `git machete help` and `git machete help <command>` for reference.

Take a look at
[https://medium.com/virtuslab/make-your-way-through-the-git-rebase-jungle-with-git-machete-e2ed4dbacd02](https://medium.com/virtuslab/make-your-way-through-the-git-rebase-jungle-with-git-machete-e2ed4dbacd02)
for a guide on how to use the tool.

The more advanced features like automated traversal, upstream inference and tree discovery are described in the second part of the series:
[https://medium.com/virtuslab/git-machete-strikes-again-traverse-the-git-rebase-jungle-even-faster-with-v2-0-f43ebaf8abb0](https://medium.com/virtuslab/git-machete-strikes-again-traverse-the-git-rebase-jungle-even-faster-with-v2-0-f43ebaf8abb0).


## Contributions

Contributions are welcome! See [contributing guidelines](CONTRIBUTING.md) for details.
Help would be especially appreciated with Python code style and refactoring - so far more focus has been put on features, documentation and automating the distribution.
