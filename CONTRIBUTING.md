# Contributing

## Run tests locally

To develop that project and run tests locally, it is needed to have Python installed with `tox`.

Use `tox -e venv` to setup virtual environment to work on that project in your favorite IDE.
Use `.tox/venv/bin/python` as a reference `python` interpreter in your IDE.

To run tests, execute `tox`.


## Command properties/classification

Deprecated commands are excluded.

Any command that can display status can also run `machete-status-branch` hook.

Any command that can run rebase can also run `machete-pre-rebase` hook.

| Property                                                          | Commands                                                                      |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| can accept interactive input on stdin                             | `add`, `delete-unmanaged`, `discover`, `go`, `traverse`, `update`             |
| can display status                                                | `discover`, `status`, `traverse`                                              |
| can modify the .git/machete file                                  | `add`, `anno`, `discover`, `edit`, `slide-out`, `traverse`                    |
| can modify the git repository (excluding .git/machete)            | `add`, `delete-unmanaged`, `go`, `reapply`, `slide-out`, `traverse`, `update` |
| can run merge                                                     | `slide-out`, `traverse`, `update`                                             |
| can run rebase                                                    | `reapply` (\*), `slide-out`, `traverse`, `update`                             |
| expects no ongoing rebase/merge/cherry-pick/revert/am             | `go`, `reapply`, `slide-out`, `traverse`, `update`                            |
| has stable output format across minor versions (plumbing command) | `file`, `fork-point` (\*\*), `is-managed`, `list`, `show`, `version`          |

(\*) `reapply` can run rebase but can't run merge since merging a branch with its own fork point is a no-op and generally doesn't make much sense.

(\*\*) Stable output is only guaranteed for `fork-point` when invoked without options or with `--inferred` option.


## Versioning

This tool is [semantically versioned](https://semver.org) with respect to all of the following:

* Python and Git version compatibility
* command-line interface (commands and their options)
* format of its specific files (currently just `machete` file within git directory)
* hooks and their interface
* output format of plumbing commands (see above for the list).

Output format of any non-plumbing command can change in non-backward-compatible manner even between patch-level updates.


## CI Docker setup reference

* https://medium.com/virtuslab/nifty-docker-tricks-for-your-ci-vol-1-c4a36d2192ea
* https://medium.com/virtuslab/nifty-docker-tricks-for-your-ci-vol-2-c5191a67f1a4

## Release TODO list

1. Merge the changes from `develop` to `master` and push `master`.

1. Make sure that build for `master` passes on [Travis CI](https://travis-ci.org/VirtusLab/git-machete/branches).

1. Verify that a build started for [Snap](https://build.snapcraft.io/user/VirtusLab/git-machete).
   If not, check build.snapcraft.io webhook on Github (under Settings > Webhooks) -
   sometimes the build system responds with 500 status for no clear reason, in such case `Redeliver` the call.
   Once ready, install the `latest/edge` revision locally (`sudo snap install --edge --classic git-machete`)
   and verify that it works correctly, esp. wrt. push/pull via ssh/https and editor (`git machete edit` and interactive rebases).

1. Run `./tag-release.sh` script to create an annotated tag for the release.
   Inspect the output of the script, i.e. the output of `git cat-file` for the newly-created tag.

1. Push tag with `git push origin <new-tag-name>` (or `git push --tags`, but the former is safer
   since it won't attempt to push any other tags that might exist locally but not in the remote).

1. Wait for the pipeline for the tag to complete successfully on [Travis CI](https://travis-ci.org/VirtusLab/git-machete/builds).

1. Verify that the latest version is uploaded to [PyPI](https://pypi.org/project/git-machete).

1. Verify that the release has been created on [Github](https://github.com/VirtusLab/git-machete/releases)
   and that a `git-machete-VERSION-1.noarch.rpm` file is present under the Assets.

   Fix the formatting in the description manually by copy-pasting the tag description
   (see [this answer](https://github.community/t5/How-to-use-Git-and-GitHub/add-release-notes-to-git-remote-tag-from-command-line/m-p/22343/highlight/true#M6488)
   for more details on why it's not automated as well).

1. Verify that a [version-bump PRs to NixOS/nixpkgs](https://github.com/NixOS/nixpkgs/pulls?q=is%3Apr+git-machete) has been opened.

1. Verify that the latest commit in [VirtusLab/homebrew-git-machete](https://github.com/VirtusLab/homebrew-git-machete) tap repo refers to the latest version.

   Re-run the latest build for `orphan/brew-package-check` branch on [Travis CI](https://travis-ci.org/VirtusLab/git-machete/branches).
   Inspect the job output and verify that the latest version gets correctly installed on Mac OS X (esp. see the output of `git machete --version`).

1. Verify that a build started on [git-machete PPA](https://launchpad.net/~virtuslab/+archive/ubuntu/git-machete/+packages).

   Once the new version package is published and the old one is removed (typically takes around 20-30 min),
   follow the instructions from [ci/deb-ppa-test-install/README.md](https://github.com/VirtusLab/git-machete/tree/master/ci/deb-ppa-test-install).
   Inspect the output of `docker-compose` and verify that the latest version gets correctly installed on Ubuntu (esp. see the output of `git machete --version`).

1. Perform a release from `latest/edge` to `latest/stable` for each architecture from [Snapcraft web dashboard](https://snapcraft.io/git-machete/releases) or via CLI.

1. Thanks to the courtesy of [Ila&iuml; Deutel](https://github.com/ilai-deutel),
   a [git-machete package](https://aur.archlinux.org/packages/git-machete) is hosted in Arch User Repository (AUR).
   If the release introduces significant changes/critical bugfixes, please [flag the package as out of date](https://aur.archlinux.org/pkgbase/git-machete/flag).
