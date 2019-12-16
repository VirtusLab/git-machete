# git-machete

[![Join the chat at https://gitter.im/VirtusLab/git-machete](https://badges.gitter.im/VirtusLab/git-machete.svg)](https://gitter.im/VirtusLab/git-machete)
[![TravisCI build status](https://api.travis-ci.org/VirtusLab/git-machete.svg?branch=master)](https://travis-ci.org/VirtusLab/git-machete)
[![PyPI package](https://badge.fury.io/py/git-machete.svg)](https://pypi.org/project/git-machete)


![](logo.png)

**git machete is a versatile tool for organizing your git repo, including features like:**

* Neat, customizable `git machete status` that shows what branches are in sync with their parent branch/remote tracking branch and which of them need to be rebased/pulled/pushed

![git machete status](https://raw.githubusercontent.com/PawelLipski/git-machete-blog-2/master/status.png)

* Semi-automatic traversal of the branches that helps you effortlessly rebase and push/pull the branches you care for (`git machete traverse`)

![git machete traverse](https://raw.githubusercontent.com/PawelLipski/git-machete-blog-2/master/traverse.png)

* Automatic discovery of branch relations (`git machete discover`)


## Install

We suggest a couple of alternative ways of installation.

**Bash and zsh completion scripts are provided** in completion/ directory, see [wiki for their installation instructions](https://github.com/VirtusLab/git-machete/wiki).

git-machete works under both Python 2.7 and Python 3.x.

### Using Debian packages (Ubuntu, Debian etc.)

See [the latest release](https://github.com/VirtusLab/git-machete/releases/latest) for downloadable .deb packages.

### Using AUR (Arch Linux only)

Install the AUR package [git-machete](https://aur.archlinux.org/packages/git-machete) using an AUR helper of your preference.

### Using Nix

On MacOS and most Linux distributions, you can install via [Nix](https://nixos.org/nix/):

```bash
# If you haven't set up any channels:
$ nix-channel --add https://nixos.org/channels/nixos-unstable unstable
$ nix-env -i git-machete
```

### Using pip with sudo (system-wide install)

You need to have Python and `pip` installed from system packages.

```bash
$ sudo -H pip install --system git-machete
```

### Using pip without sudo (user-wide install)

You need to have Python and `pip` installed from system packages.

```bash
$ pip install git-machete
```

Please verify that your `PATH` variable has `${HOME}/.local/bin/` included.

### Using make with sudo (deprecated)

Run the following commands to install git machete:

```bash
$ git clone --depth=1 https://github.com/VirtusLab/git-machete.git
$ cd git-machete
$ sudo make install
```


## Quick start

```bash
$ cd your-repo/
$ git machete discover --checked-out-since='2 weeks ago'  # increase/decrease the timespan if you want more/less old branches included
  # (see and possibly edit the suggested layout of branches - branch layout is always kept as text file .git/machete)
$ git machete go root
$ git machete traverse
  # (put each branch one by one in sync with its parent and remote counterpart)
```


## Reference

Take a look at
[https://medium.com/virtuslab/make-your-way-through-the-git-rebase-jungle-with-git-machete-e2ed4dbacd02](https://medium.com/virtuslab/make-your-way-through-the-git-rebase-jungle-with-git-machete-e2ed4dbacd02)
for a guide on how to use the tool.

The more advanced features like automated traversal, upstream inference and tree discovery are described in the second part of the series:
[https://medium.com/virtuslab/git-machete-strikes-again-traverse-the-git-rebase-jungle-even-faster-with-v2-0-f43ebaf8abb0](https://medium.com/virtuslab/git-machete-strikes-again-traverse-the-git-rebase-jungle-even-faster-with-v2-0-f43ebaf8abb0).


## Contribute

To develop that project and run tests locally it is needed to have Python installed with `tox`.

Use `tox -e venv` to setup virtual environment to work on that project in your favorite IDE. Use `.tox/venv/bin/python` as a reference `python` interpreter in your IDE.

To run tests execute command `tox`.
