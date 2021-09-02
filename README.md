# git-machete

[![Join the chat at https://gitter.im/VirtusLab/git-machete](https://badges.gitter.im/VirtusLab/git-machete.svg)](https://gitter.im/VirtusLab/git-machete)
[![CircleCI](https://circleci.com/gh/VirtusLab/git-machete/tree/master.svg?style=shield)](https://app.circleci.com/pipelines/github/VirtusLab/git-machete?branch=master)
[![PyPI package](https://img.shields.io/pypi/v/git-machete.svg)](https://pypi.org/project/git-machete)
[![PyPI package monthly downloads](https://img.shields.io/pypi/dm/git-machete.svg)](https://pypistats.org/packages/git-machete)
[![Snap](https://snapcraft.io/git-machete/badge.svg)](https://snapcraft.io/git-machete)
[![License: MIT](https://img.shields.io/github/license/VirtusLab/git-machete)](https://github.com/VirtusLab/git-machete/blob/master/LICENSE)

<img src="https://raw.githubusercontent.com/VirtusLab/git-machete/develop/graphics/logo_with_name.svg"; style="width: 100%; display: block; margin-bottom: 10pt;" />
<!-- The image is referenced by full URL, corresponding develop branch to ensure it renders correctly on https://pypi.org/project/git-machete/ -->

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
    <img src="https://raw.githubusercontent.com/VirtusLab/git-machete/develop/graphics/discover-status-traverse.gif"
         alt="git machete discover, status and traverse" />
</p>
<!-- The gif in here is referenced by full URL, corresponding develop branch to ensure it renders correctly on https://pypi.org/project/git-machete/ -->

🔌 See also [VirtusLab/git-machete-intellij-plugin](https://github.com/VirtusLab/git-machete-intellij-plugin#git-machete-intellij-plugin) &mdash;
a port into a plugin for the IntelliJ Platform products, including PyCharm, WebStorm etc.


## Install

We suggest a couple of alternative ways of installation.

### Bash

#### Mac (via Homebrew)

Make sure you have bash completion installed (with `brew install bash-completion`).

`brew install git-machete` automatically installs bash completion files for `git machete`.


#### Linux

1. In a non-minimal installation of Linux, bash completion should be available.
2. Place the completion script in `/etc/bash_completion.d/`.

```shell script
sudo curl -L https://raw.githubusercontent.com/VirtusLab/git-machete/master/completion/git-machete.completion.bash -o /etc/bash_completion.d/git-machete
```


### Zsh

#### Linux/Mac: with [oh-my-zsh](https://ohmyz.sh/) shell

```shell script
$ mkdir -p ~/.oh-my-zsh/custom/plugins/git-machete/
$ curl -L https://raw.githubusercontent.com/VirtusLab/git-machete/master/completion/git-machete.completion.zsh -o ~/.oh-my-zsh/custom/plugins/git-machete/git-machete.plugin.zsh
```

Add `git-machete` to the plugins list in `~/.zshrc` to run autocompletion within the oh-my-zsh shell.
In the following example, `...` represents other zsh plugins you may have installed.

```shell script
plugins=(... git-machete
)
```

##### Workarounds for Zsh on Mac

On Mac, unfortunately there might be a problem that `git machete` subcommands still don't complete even when the zsh plugin is active.
This issue also affects other non-standard `git` subcommands like `git flow` and `git lfs`.
To work the issue around, first establish how `git` is installed in your system.
```shell script
which git
```

If `git` resolves to `/usr/bin/git`, then likely `git` is the default installation provided in Mac OS.
As a workaround, add the following line directly at the end of `~/.zshrc`:
```shell script
source ~/.oh-my-zsh/custom/plugins/git-machete/git-machete.plugin.zsh
```
and reload the shell.

If `git` resolves to `/usr/local/bin/git`, then likely `git` has been installed via `brew`.
Up to our current knowledge, workaround is much harder to provide in such scenario.
One option is to `brew uninstall git` and then use the solution for Mac's default `git` provided above,
but that's likely undesired since `git` shipped with Mac OS is almost always an older version than what's available via `brew`.
Another, less intrusive workaround is to make sure that the zsh `_git` function
is NOT taken from brew-git's `/usr/local/share/zsh/site-functions/_git`,
but instead from `/usr/share/zsh/5.7.1/functions/_git` (zsh version path fragment can be different from `5.7.1`).
Add the following at the end of `~/.zshrc`:
```shell script
source /usr/share/zsh/5.7.1/functions/_git  # or other zsh version instead of 5.7.1, depending on what's available in the system
```
and reload the shell.


#### Linux/Mac: without oh-my-zsh shell

1. Place the completion script in your `/path/to/zsh/completion` (typically `~/.zsh/completion/`):

```shell script
$ mkdir -p ~/.zsh/completion
$ curl -L https://raw.githubusercontent.com/VirtusLab/git-machete/master/completion/git-machete.completion.zsh -o ~/.zsh/completion/_git-machete
```

2. Include the directory in your `$fpath` by adding in `~/.zshrc`:

```shell script
fpath=(~/.zsh/completion $fpath)
```

3. Make sure `compinit` is loaded or do it by adding in `~/.zshrc`:

```shell script
autoload -Uz compinit && compinit -i
```

4. Then reload your shell:

```shell script
exec $SHELL -l
```

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

Annotate the branches with GitHub PR numbers: <br/>
```shell script
git machete github anno-prs
```

Create the PR, using the upstream (parent) branch from `.git/machete` as the base: <br/>
```shell script
git machete github create-pr [--draft]
```

Sets the base of the current branch's PR to its upstream (parent) branch, as seen by git machete: <br/>
```shell script
git machete github retarget-pr
```

**Note**: for private repositories, a GitHub API token with `repo` access is required.
This will be resolved from the first of:
1. The `GITHUB_TOKEN` env var.
2. The auth token from the current [`gh`](https://cli.github.com/) configuration.
3. The auth token from the current [`hub`](https://github.com/github/hub) configuration.

<br/>

## Reference

See `git machete help` and `git machete help <command>` for reference.

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
