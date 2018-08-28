# git-machete

If you work a with a git rebase flow, git machete will (vastly!) help you manage the jungle of branches stacking on top of each other when you're, for example, working on a couple of different PRs in parallel.

![git machete status](https://raw.githubusercontent.com/PawelLipski/git-machete-blog-2/master/status.png)

## Install

Run the following commands to install git machete:

```bash
$ git clone https://github.com/VirtusLab/git-machete.git
$ cd git-machete
$ sudo make install
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
