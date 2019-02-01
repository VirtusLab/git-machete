# git-machete

[![Join the chat at https://gitter.im/VirtusLab/git-machete](https://badges.gitter.im/VirtusLab/git-machete.svg)](https://gitter.im/VirtusLab/git-machete?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

[![TravisCI build status](https://api.travis-ci.org/VirtusLab/git-machete.svg?branch=master)](https://travis-ci.org/VirtusLab/git-machete)

![](logo.png)

If you work a with a git rebase flow, git machete will (vastly!) help you manage the jungle of branches stacking on top of each other when you're, for example, working on a couple of different PRs in parallel.

![git machete status](https://raw.githubusercontent.com/PawelLipski/git-machete-blog-2/master/status.png)

## Install

### Using make

Run the following commands to install git machete:

```bash
$ git clone https://github.com/VirtusLab/git-machete.git
$ cd git-machete
$ sudo make install
```

### Using setup

Run the following commands to install git machete:

```bash
$ git clone https://github.com/VirtusLab/git-machete.git
$ cd git-machete
$ python setup.py install
```

To install you need to have Python with installed `pip` and `setuptools`. Recommended Python env is installed with [Pyenv](https://github.com/pyenv/pyenv).

Support Python version is `python2.*`. `python3.*` is not yet support. Support for version 3 is addressed in issue #35.

If you use system Python env, you will need to execute last command with `sudo` or with option `--user`:

```bash
$ sudo python setup.py install

$ python setup.py install --user
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

## Contribute

To develop that project and run tests locally it is needed to have Python installed with `tox`.

Use `tox -e venv` to setup virtual environment to work on that project in your favorite IDE. Use `.tox/venv/bin/python` as a reference `python` interpreter in your IDE.

To run tests execute command `tox`.

## Reference

Take a look at [https://virtuslab.com/blog/make-way-git-rebase-jungle-git-machete/](https://virtuslab.com/blog/make-way-git-rebase-jungle-git-machete/) for a guide on how to use the tool.

The more advanced features like automated traversal, upstream inference and tree discovery are described in the second part of the series:
[https://virtuslab.com/blog/git-machete-strikes-traverse-git-rebase-jungle-even-faster-v2-0/](https://virtuslab.com/blog/git-machete-strikes-traverse-git-rebase-jungle-even-faster-v2-0/)
