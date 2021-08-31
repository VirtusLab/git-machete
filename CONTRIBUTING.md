# Contributing

## Run tests locally

To develop that project and run tests locally, it is needed to have Python installed with `tox`.

Use `tox -e venv` to setup virtual environment to work on that project in your favorite IDE.
Use `.tox/venv/bin/python` as a reference `python` interpreter in your IDE.

To run tests, execute `tox`.


## Generate sandbox repositories

Run `docs/setup-sandbox` script to set up a test repo under `~/machete-sandbox` with a remote in `~/machete-sandbox-remote`.


## Command properties/classification

Deprecated commands are excluded.

| Property                                                          | Commands                                                                                                                                       |
| ----------------------------------------------------------------- | -----------------------------------------------------------------------------------------------------------------------------------------------|
| can accept interactive input on stdin                             | `add`, `advance`, `delete-unmanaged`, `discover`,`github`<sup>[1]</sup>, `go`, `traverse`, `update`                                            |
| can display status (and run `machete-status-branch` hook)         | `discover`, `github`<sup>[1]</sup>, `status`, `traverse`                                                                                       |
| can modify the .git/machete file                                  | `add`, `advance`, `anno`, `discover`, `edit`, `github`, `slide-out`, `traverse`                                                                |
| can modify the git repository (excluding .git/machete)            | `add`, `advance`, `delete-unmanaged`, `github`<sup>[1]</sup>, `go`, `reapply`, `slide-out`, `squash`, `traverse`, `update`                     |
| can run merge                                                     | `advance`<sup>[2]</sup>, `slide-out`, `traverse`, `update`                                                                                     |
| can run rebase (and run `machete-pre-rebase` hook)                | `reapply`<sup>[3]</sup>, `slide-out`, `traverse`, `update`                                                                                     |
| can slide out a branch (and run `machete-post-slide-out` hook)    | `advance`, `slide-out`, `traverse`                                                                                                             |
| expects no ongoing rebase/merge/cherry-pick/revert/am             | `advance`, `go`, `reapply`, `slide-out`, `squash`, `traverse`, `update`                                                                        |
| has stable output format across minor versions (plumbing command) | `file`, `fork-point`<sup>[4]</sup>, `is-managed`, `list`, `show`, `version`                                                                    |

[1]: `github` can only display status, accept interactive mode or modify git repository when `create-pr` subcommand is passed and the current branch is untracked or ahead of its remote.

[2]: `advance` can only run fast-forward merge (`git merge --ff-only`).

[3]: `reapply` can run rebase but can't run merge since merging a branch with its own fork point is a no-op and generally doesn't make much sense.

[4]: A stable output is only guaranteed for `fork-point` when invoked without any option or only with `--inferred` option.


## Versioning

This tool is [semantically versioned](https://semver.org) with respect to all of the following:

* Python and Git version compatibility
* command-line interface (commands and their options)
* format of its specific files (currently just `machete` file within git directory)
* hooks and their interface
* output format of plumbing commands (see above for the list).

Output format of any non-plumbing command can change in non-backward-compatible manner even between patch-level updates.


## CI Docker setup reference

* [Nifty Docker tricks for your CI (vol. 1)](https://medium.com/virtuslab/nifty-docker-tricks-for-your-ci-vol-1-c4a36d2192ea)
* [Nifty Docker tricks for your CI (vol. 2)](https://medium.com/virtuslab/nifty-docker-tricks-for-your-ci-vol-2-c5191a67f1a4)


## Release TODO list

1. Merge the changes from `develop` to `master` and push `master`.

1. Verify that the release has been created on [Github](https://github.com/VirtusLab/git-machete/releases)
   and that a `git-machete-<VERSION>-1.noarch.rpm` file is present under the Assets.

1. Verify that the latest version is uploaded to [PyPI](https://pypi.org/project/git-machete).

1. Verify that the latest commit in [VirtusLab/homebrew-git-machete](https://github.com/VirtusLab/homebrew-git-machete) tap repo refers to the latest version.

1. Verify that a build started for [Snap](https://build.snapcraft.io/user/VirtusLab/git-machete).
   If not, check `build.snapcraft.io` webhook on Github (under Settings > Webhooks) -
   sometimes the Snap Store's build system responds with 500 status for no clear reason, in such case `Redeliver` the call.

   Once ready, install the `latest/edge` revision locally (`sudo snap install --edge --classic git-machete`)
   and verify that it works correctly, esp. wrt. push/pull via ssh/https and editor (`git machete edit` and interactive rebases).

   Then, perform a release from `latest/edge` to `latest/stable` for both `i386` and `amd64`
   from [Snapcraft web dashboard](https://snapcraft.io/git-machete/releases) or via CLI.

1. Verify that a build started on [git-machete PPA](https://launchpad.net/~virtuslab/+archive/ubuntu/git-machete/+packages).

   Once the new version of package is published and the old one is removed (typically takes around 20-30 min),
   follow the instructions from [ci/deb-ppa-test-install/README.md](https://github.com/VirtusLab/git-machete/tree/master/ci/deb-ppa-test-install).
   Inspect the output of `docker-compose` and verify that the latest version gets correctly installed on Ubuntu (esp. see the output of `git machete --version`).

1. Thanks to the courtesy of [@blitz (Julian Stecklina)](https://github.com/blitz),
   a [git-machete package](https://github.com/NixOS/nixpkgs/blob/master/pkgs/applications/version-management/git-and-tools/git-machete/default.nix)
   lives in [Nixpkgs](https://github.com/NixOS/nixpkgs) &mdash; the collection of packages for [Nix package manager](https://nixos.org/).

   Since @blitz's [PR #131141 to NixOS/nixpkgs](https://github.com/NixOS/nixpkgs/pull/131141),
   automatic updates of this package (based on the package hosted on PyPI) should be performed by [@r-ryantm bot](https://github.com/r-ryantm).
   Verify that [version-bump PRs to NixOS/nixpkgs](https://github.com/NixOS/nixpkgs/pulls?q=is%3Apr+git-machete),
   are regularly opened so that Nix package is kept up to date with git-machete releases.

1. Thanks to the courtesy of [Ila&iuml; Deutel](https://github.com/ilai-deutel),
   a [git-machete package](https://aur.archlinux.org/packages/git-machete) is hosted in Arch User Repository (AUR).
   If the release introduces significant changes/critical bugfixes, please [flag the package as out of date](https://aur.archlinux.org/pkgbase/git-machete/flag).
<!--
1. Verify that changes you made in files holding blogs content are reflected in the corresponding medium articles. Files and corresponding to them articles:
   * [blogs/git-machete-1/blog.md](https://github.com/VirtusLab/git-machete/blob/develop/blogs/git-machete-1/blog.md) - [Make your way through the git (rebase) jungle with Git Machete](https://medium.com/virtuslab/make-your-way-through-the-git-rebase-jungle-with-git-machete-e2ed4dbacd02);
   * [blogs/git-machete-2/blog.md](https://github.com/VirtusLab/git-machete/blob/develop/blogs/git-machete-2/blog.md) - [Git Machete Strikes again!](https://medium.com/virtuslab/git-machete-strikes-again-traverse-the-git-rebase-jungle-even-faster-with-v2-0-f43ebaf8abb0);
   * [blogs/docker-ci-tricks-1/blog.md](https://github.com/VirtusLab/git-machete/blob/develop/blogs/docker-ci-tricks-1/blog.md) - [Nifty Docker tricks for your CI (vol. 1)](https://medium.com/virtuslab/nifty-docker-tricks-for-your-ci-vol-1-c4a36d2192ea);
   * [blogs/docker-ci-tricks-2/blog.md](https://github.com/VirtusLab/git-machete/blob/develop/blogs/docker-ci-tricks-2/blog.md) - [Nifty Docker tricks for your CI (vol. 2)](https://medium.com/virtuslab/nifty-docker-tricks-for-your-ci-vol-2-c5191a67f1a4).
-->
   If not, please apply changes on Medium to keep consistency.
Since Medium does not offer conversion directly from Markdown, copy the formatted blog text from a GitHub and paste it into the Medium rich text editor.
