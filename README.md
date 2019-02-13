# git-machete

[![Join the chat at https://gitter.im/VirtusLab/git-machete](https://badges.gitter.im/VirtusLab/git-machete.svg)](https://gitter.im/VirtusLab/git-machete)
[![TravisCI build status](https://api.travis-ci.org/VirtusLab/git-machete.svg?branch=master)](https://travis-ci.org/VirtusLab/git-machete)

![](logo.png)

**git machete is a versatile tool for organizing your git repo, including features like:**

* Automatic discovery of branch relations (`git machete discover`)

* Neat, customizable `git machete status` that shows what branches are in sync with their parent branch/remote tracking branch and which of them need to be rebased/pulled/pushed

![git machete status](https://raw.githubusercontent.com/PawelLipski/git-machete-blog-2/master/status.png)

* Semi-automatic traversal of the branches that helps you effortlessly rebase and push/pull the branches you care for (`git machete traverse`)

![git machete traverse](https://raw.githubusercontent.com/PawelLipski/git-machete-blog-2/master/traverse.png)


## Install

We suggest 3 alternative ways of installation to make sure at least one works for you ;)

Note: as for now git-machete runs on Python 2.7, we're planning to migrate to Python 3 soon (#35).
Only bash completion is supported as for now (#21 for zsh).

### Using make with sudo

Run the following commands to install git machete:

```bash
$ git clone https://github.com/VirtusLab/git-machete.git
$ cd git-machete
$ sudo make install
```

### Using setup.py with sudo

You need to have Python from system packages with `pip` and `setuptools` installed.

```bash
$ git clone https://github.com/VirtusLab/git-machete.git
$ cd git-machete
$ python setup.py build
$ sudo python setup.py install
```
You may need to ensure that Bash actually sources the completion scripts from `/etc/bash_completion.d/` or `/usr/local/etc/bash_completion.d/`.

### Using setup.py without sudo

You need to have Python from system packages with `pip` and `setuptools` installed.

```bash
$ git clone https://github.com/VirtusLab/git-machete.git
$ cd git-machete
$ python setup.py install --user
```

Please verify that your `PATH` variable has `${HOME}/.local/bin/` included.
Also, ensure that you have sourced files from `${HOME}/.local/etc/bash_completion.d/` in your bash completion config.
You can do it explicitly for git-machete by simply adding the following line to your .bashrc:

```bash
. ~/.local/etc/bash_completion.d/git-machete-prompt
```


## Quick start

```bash
$ cd your-repo/
$ git machete discover
  # (see and possibly edit the suggested layout of branches)
$ git machete go root
$ git machete traverse
  # (put each branch one by one in sync with its parent and remote counterpart)
```


## Reference

Take a look at [https://virtuslab.com/blog/make-way-git-rebase-jungle-git-machete/](https://virtuslab.com/blog/make-way-git-rebase-jungle-git-machete/) for a guide on how to use the tool.

The more advanced features like automated traversal, upstream inference and tree discovery are described in the second part of the series:
[https://virtuslab.com/blog/git-machete-strikes-traverse-git-rebase-jungle-even-faster-v2-0/](https://virtuslab.com/blog/git-machete-strikes-traverse-git-rebase-jungle-even-faster-v2-0/)


## Contribute

To develop that project and run tests locally it is needed to have Python installed with `tox`.

Use `tox -e venv` to setup virtual environment to work on that project in your favorite IDE. Use `.tox/venv/bin/python` as a reference `python` interpreter in your IDE.

To run tests execute command `tox`.
