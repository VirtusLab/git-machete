# git-machete

[![Read the Docs](https://readthedocs.org/projects/git-machete/badge/?version=latest)](https://git-machete.readthedocs.io/en/stable)
[![PyPI package](https://img.shields.io/pypi/v/git-machete.svg)](https://pypi.org/project/git-machete)
[![PyPI package monthly downloads](https://img.shields.io/pypi/dm/git-machete.svg?label=pypi%20downloads)](https://pypistats.org/packages/git-machete)
[![Snap](https://snapcraft.io/git-machete/badge.svg)](https://snapcraft.io/git-machete)
[![AUR package (Arch Linux)](https://repology.org/badge/version-for-repo/aur/git-machete.svg)](https://aur.archlinux.org/packages/git-machete)
[![License: MIT](https://img.shields.io/github/license/VirtusLab/git-machete)](https://github.com/VirtusLab/git-machete/blob/master/LICENSE)
[![CircleCI](https://circleci.com/gh/VirtusLab/git-machete/tree/master.svg?style=shield)](https://app.circleci.com/pipelines/github/VirtusLab/git-machete?branch=master)
[![codecov](https://codecov.io/gh/VirtusLab/git-machete/branch/master/graph/badge.svg)](https://codecov.io/gh/VirtusLab/git-machete)

<img src="https://raw.githubusercontent.com/VirtusLab/git-machete/master/graphics/logo_with_name.svg" style="width: 100%; display: block; margin-bottom: 10pt;" />
<!-- The image is referenced by its full URL to ensure it renders correctly on https://pypi.org/project/git-machete/ -->

💪 git-machete is a robust tool that **simplifies your git workflows**.<br/>

🦅 The _bird's eye view_ provided by git-machete makes **merges/rebases/push/pulls hassle-free**
even when **multiple branches** are present in the repository
(master/develop, your topic branches, teammate's branches checked out for review, etc.).<br/>

🎯 Using this tool, you can maintain **small, focused, easy-to-review pull requests** with little effort.

👁 A look at a `git machete status` gives an instant answer to the questions:
* What branches are in this repository?
* What is going to be merged (rebased/pushed/pulled) and to what?

🚜 `git machete traverse` semi-automatically traverses the branches, helping you effortlessly rebase, merge, push and pull.

<p align="center">
    <img src="https://raw.githubusercontent.com/VirtusLab/git-machete/master/graphics/discover-status-traverse.gif"
         alt="git machete discover, status and traverse" />
</p>
<!-- The image is referenced by its full URL to ensure it renders correctly on https://pypi.org/project/git-machete/ -->

🔌 See also [VirtusLab/git-machete-intellij-plugin](https://github.com/VirtusLab/git-machete-intellij-plugin#git-machete-intellij-plugin) &mdash;
a port into a plugin for the IntelliJ Platform products, including PyCharm, WebStorm etc.


## Install

We suggest a couple of alternative ways of installation.

**Instructions for installing bash, zsh, and fish completion scripts are provided in [completion/README.md](completion/README.md).**

git-machete requires Python >= 3.6. Python 2.x is no longer supported.

### Using Homebrew (macOS)

```shell script
brew tap VirtusLab/git-machete
brew install git-machete
```

### Using Snappy (most Linux distributions)

**Tip:** check the [guide on installing snapd](https://snapcraft.io/docs/installing-snapd) if you don't have Snap support set up yet in your system.

```shell script
sudo snap install --classic git-machete
```

It can also be installed via Ubuntu Software (simply search for `git-machete`).

**Note:** classic confinement is necessary to ensure access to the editor installed in the system (to edit e.g. .git/machete file or rebase TODO list).

### Using PPA (Ubuntu)

**Tip:** run `sudo apt-get install -y software-properties-common` first if `add-apt-repository` is not available on your system.

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

**Note:** since `nixos-21.05`, `git-machete` is included in the stable channels as well.
The latest released version, however, is generally available in the unstable channel.
Stable channels may lag behind; see [repology](https://repology.org/project/git-machete/versions) for the current channel-package mapping.

### Using pip with sudo (system-wide install)

You need to have Python and `pip` installed from system packages.

```shell script
sudo -H pip install git-machete
```

**Tip:** pass an extra `-U` flag to `pip install` to upgrade an already installed version.

### Using pip without sudo (user-wide install)

You need to have Python and `pip` installed from system packages.

```shell script
pip install --user git-machete
```

Please verify that your `PATH` variable has `${HOME}/.local/bin/` included.

**Tip:** pass an extra `-U` flag to `pip install` to upgrade an already installed version.

<br/>

## Quick start

### Discover the branch layout

```shell script
cd your-repo/
git machete discover
```

See and possibly edit the suggested layout of branches.
Branch layout is always kept as a `.git/machete` text file.

### See the current repository state
```shell script
git machete status --list-commits
```

**Green** edge means the given branch is **in sync** with its parent. <br/>
**Red** edge means it is **out of sync** &mdash; parent has some commits that the given branch does not have. <br/>
**Gray** edge means that the branch is **merged** to its parent.

### Rebase, reset to remote, push, pull all branches as needed
```shell script
git machete traverse --fetch --start-from=first-root
```

Put each branch one by one in sync with its parent and remote tracking branch.

### Fast-forward current branch to match a child branch
```shell script
git machete advance
```

Useful for merging the child branch to the current branch in a linear fashion (without creating a merge commit).

### GitHub integration

Check out the given PRs into local branches, also traverse chain of pull requests upwards, adding branches one by one to git-machete and check them out locally as well: <br/>
```shell script
git machete github checkout-prs [--all | --by=<github-login> | --mine | <PR-number-1> ... <PR-number-N>]
```

Create the PR, using the upstream (parent) branch from `.git/machete` as the base: <br/>
```shell script
git machete github create-pr [--draft]
```

Synchronize with the remote repository: checkout your open PRs, delete unmanaged branches and also delete untracked managed branches with no downstream branch: <br/>
```shell script
git machete github sync
```

**Note**: for private repositories, a GitHub API token with `repo` access is required.
This will be resolved from the first of:
1. The `GITHUB_TOKEN` env var.
2. The content of the .github-token file in the home directory (`~`). This file has to be manually created by the user.
3. The auth token from the current [`gh`](https://cli.github.com/) configuration.
4. The auth token from the current [`hub`](https://github.com/github/hub) configuration.

<br/>

## Reference

Find the docs at [Read the Docs](https://git-machete.readthedocs.io/).
You can also check `git machete help` and `git machete help <command>`.

Take a look at
[reference blog post](https://medium.com/virtuslab/make-your-way-through-the-git-rebase-jungle-with-git-machete-e2ed4dbacd02)
for a guide on how to use the tool.

The more advanced features like automated traversal, upstream inference and tree discovery are described in the
[second part of the series](https://medium.com/virtuslab/git-machete-strikes-again-traverse-the-git-rebase-jungle-even-faster-with-v2-0-f43ebaf8abb0).


## Git compatibility

git-machete (since version 2.13.0) is compatible with git >= 1.8.0.


## Contributions

Contributions are welcome! See [contributing guidelines](CONTRIBUTING.md) for details.
Help would be especially appreciated with Python code style and refactoring &mdash;
so far more focus has been put on features, documentation and automating the distribution.
