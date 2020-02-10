# Contributing

## Run tests locally

To develop that project and run tests locally, it is needed to have Python installed with `tox`.

Use `tox -e venv` to setup virtual environment to work on that project in your favorite IDE.
Use `.tox/venv/bin/python` as a reference `python` interpreter in your IDE.

To run tests, execute `tox`.


## Command properties/classification

| Property                                                          | Commands                                                                      |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| can accept interactive input on stdin                             | `add`, `delete-unmanaged`, `discover`, `go`, `traverse`, `update`             |
| can display status                                                | `discover`, `status`, `traverse`                                              |
| can modify the .git/machete file                                  | `add`, `anno`, `discover`, `edit`, `slide-out`, `traverse`                    |
| can modify the git repository (excluding .git/machete)            | `add`, `delete-unmanaged`, `go`, `reapply`, `slide-out`, `traverse`, `update` |
| can run merge                                                     | `slide-out`, `traverse`, `update`                                             |
| can run rebase                                                    | `reapply`, `slide-out`, `traverse`, `update`                                  |
| has stable output format across minor versions (plumbing command) | `file`, `fork-point`, `list`, `show`, `version`                               |

Deprecated commands are excluded.

Any command that can display status can also run `machete-status-branch` hook.

Any command that can run rebase can also run `machete-pre-rebase` hook.

`reapply` can run rebase but can't run merge since merging a branch with its own fork point can always be performed in fast-forward manner and generally doesn't make much sense.


## Versioning

This tool is [semantically versioned](https://semver.org) with respect to all of the following:

* Python and Git version compatibility
* command-line interface (commands and their options)
* format of its specific files (currently just `machete` file within git directory)
* hooks and their interface
* output format of plumbing commands (see above for the list).

Output format of any non-plumbing command can change in non-backward-compatible manner even between patch-level updates.


## Release

Check out `master` branch locally.
Make sure `master` is up to date with `origin/master` and that build for `master` passes on [Travis CI](https://travis-ci.org/VirtusLab/git-machete/branches).

Run `./tag-release.sh` script to create annotated tag for the release.
Inspect the output of the script, i.e. the output of `git cat-file` for the newly-created tag.

Push tag with `git push origin <new-tag-name>` (or `git push --tags`, but the former is safer
since it won't attempt to push any other tags that might exist locally but not in the remote).

Wait for the pipeline for the tag to complete successfully on [Travis CI](https://travis-ci.org/VirtusLab/git-machete/builds).

Verify that the release has been created on [Github](https://github.com/VirtusLab/git-machete/releases) with correct name and release notes,
and that a `git-machete-VERSION-1.noarch.rpm` file is present under the Assets.

Verify that the latest version is uploaded to [PyPI](https://pypi.org/project/git-machete/).

Verify that the latest commit in [VirtusLab/homebrew-git-machete](https://github.com/VirtusLab/homebrew-git-machete) tap repo refers to the latest version.
Re-run the latest build for `orphan/brew-package-check` branch on [Travis CI](https://travis-ci.org/VirtusLab/git-machete/branches).
Inspect the job output and verify that the latest version gets correctly installed on Mac OS X (esp. see the output of `git machete --version`).

Verify that a build started on [git-machete PPA](https://launchpad.net/~virtuslab/+archive/ubuntu/git-machete/+packages).
Once the new version package is published and the old one is removed (typically takes around 20-30 min),
follow the instructions from [ci/apt-ppa-test-install/README.md](https://github.com/VirtusLab/git-machete/tree/master/ci/apt-ppa-test-install).
Inspect the output of `docker-compose` and verify that the latest version gets correctly installed on Ubuntu (esp. see the output of `git machete --version`).

Thanks to the courtesy of [Ila&iuml; Deutel](https://github.com/ilai-deutel),
a [git-machete package](https://aur.archlinux.org/packages/git-machete/) is hosted in Arch User Repository (AUR).
If the release introduces significant changes/critical bugfixes, please [flag the package as out of date](https://aur.archlinux.org/pkgbase/git-machete/flag/).

A [git-machete package](https://aur.archlinux.org/packages/git-machete/) is available for NixOS.
[Version-bump PRs to NixOS/nixpkgs](https://github.com/NixOS/nixpkgs/pulls?q=is%3Apr+git-machete) are opened by a semi-automatic update on an irregular basis.
There is an issue ([#79](https://github.com/VirtusLab/git-machete/issues/79)) for opening version-bump PRs automatically on each release.
