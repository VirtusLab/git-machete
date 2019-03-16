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

git-machete requires Python 3.

We suggest 3 alternative ways of installation.

**Bash and zsh completion scripts are provided** in completion/ directory, see [wiki for their installation instructions](https://github.com/VirtusLab/git-machete/wiki).

### Using make with sudo

Run the following commands to install git machete:

```bash
$ git clone --depth=1 https://github.com/VirtusLab/git-machete.git
$ cd git-machete
$ sudo make install
```

### Using setup.py with sudo

You need to have Python from system packages with `pip` and `setuptools` installed.

```bash
$ git clone --depth=1 https://github.com/VirtusLab/git-machete.git
$ cd git-machete
$ python setup.py build
$ sudo python setup.py install
```

### Using setup.py without sudo

You need to have Python from system packages with `pip` and `setuptools` installed.

```bash
$ git clone --depth=1 https://github.com/VirtusLab/git-machete.git
$ cd git-machete
$ python setup.py install --user
```

Please verify that your `PATH` variable has `${HOME}/.local/bin/` included.


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
