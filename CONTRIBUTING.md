# Contributing

## PyCharm setup

Make sure the following bundled plugins are enabled:
* Docker
* Git
* Markdown
* Ini
* IntelliLang (for language injections, e.g. Markdown/shell scripts in YAML)
* ReStructuredText
* Shell Script (also: agree to enable Shellcheck when asked)
* YAML

Optionally, you can also install the following non-bundled plugins from Marketplace:
* [AWK Support](https://plugins.jetbrains.com/plugin/17037-awk-support)
* [NixIDEA](https://plugins.jetbrains.com/plugin/8607-nixidea)
* [Requirements](https://plugins.jetbrains.com/plugin/10837-requirements/)


## Git setup

From the main project folder, run the following commands:

```shell
ln -s ../../hook_samples/machete-status-branch .git/hooks/machete-status-branch
ln -s ../../hook_samples/post-commit .git/hooks/post-commit
ln -s ../../ci/checks/run-all-checks.sh .git/hooks/pre-commit
```


## Run tests locally

To develop that project and run tests locally, it is needed to have Python installed with `tox`.

Use `tox -e venv` to setup virtual environment to work on that project in your favorite IDE.
Use `.tox/venv/bin/python` as a reference `python` interpreter in your IDE.

To run tests, execute `tox`.

It's also possible to execute tests graphically in PyCharm (right-clicking on the test file
or clicking the green triangle on the left of the test case name), which can be very useful when debugging a single test case.
To do so, make sure that the libraries from [requirements.testenv.txt](requirements.testenv.txt) are installed in the current venv.


## Generate sandbox repositories

Run [`graphics/setup-sandbox`](graphics/setup-sandbox) script to set up a test repo under `~/machete-sandbox` with a remote in `~/machete-sandbox-remote`.

## Regenerate the GIF in README.md

1. Generate sandbox repositories as shown above and `cd` into `~/machete-sandbox`.
1. Install [asciinema](https://github.com/asciinema/asciinema), [asciicast2gif](https://github.com/asciinema/asciicast2gif)
   and their dependencies.
1. Run [`graphics/generate-asciinema-gif`](graphics/generate-asciinema-gif) (It will print the location of the generated GIF file)
1. Replace existing GIF [`graphics/discover-status-traverse.gif`](graphics/discover-status-traverse.gif) with the new one.

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

[1]: `github` can only display status, accept interactive mode or modify git repository when `create-pr` or `checkout-prs` subcommand is passed.

[2]: `advance` can only run fast-forward merge (`git merge --ff-only`).

[3]: `reapply` can run rebase but can't run merge since merging a branch with its own fork point is a no-op and generally doesn't make much sense.

[4]: A stable output is only guaranteed for `fork-point` when invoked without any option or only with `--inferred` option.


## Versioning

This tool is [semantically versioned](https://semver.org) with respect to all of the following:

* Python and Git version compatibility
* command-line interface (commands and their options)
* format of its specific files (currently just `machete` file within git directory)
* hooks and their interface
* output format of plumbing commands (see above for the list)
* accepted environment variables

Output format of any [non-plumbing command](#command-propertiesclassification) can change in a non-backward-compatible manner even between patch-level updates.


## CI Docker setup reference

* [Nifty Docker tricks for your CI (vol. 1)](https://medium.com/virtuslab/nifty-docker-tricks-for-your-ci-vol-1-c4a36d2192ea)
* [Nifty Docker tricks for your CI (vol. 2)](https://medium.com/virtuslab/nifty-docker-tricks-for-your-ci-vol-2-c5191a67f1a4)


## FAQ about Pull Requests

#### What is the proper base for pull request?

Please set the base of pull request to `develop` branch.
Current branch protection rules on GitHub only allow to merge `develop` or `hotfix/*` branches into `master`.

#### Who closes GitHub comments? Author of changes, reviewer or initiator of the conversation?

It makes sense to close comment:

1) If the comment was trivial and was addressed as suggested by the reviewer,
   then it is enough for the PR author to simply `Resolve` the thread and that's it.
2) If the comment was not trivial and/or for some reason the PR author believes that the comment should not be addressed as suggested by the reviewer,
   then it is best to leave the thread open after replying; then the reviewer can press `Resolve` once they have decided that the matter is cleared.

#### Do you make squash before develop?

Any technique is okay as long as there are [NO unnecessary merge commits](https://slides.com/plipski/git-machete#/8).
`Squash and merge` from GitHub is okay, fast-forward made from console or via `git machete advance` is okay too.

#### Is there any commit message convention?

Nothing special, as long as they look neat in the sense that they are written in the [imperative form](https://cbea.ms/git-commit/#imperative)
and describe what actually happened on a given commit.

#### How do you know that the comment has been approved?

As in the first point, if the PR author accepts the suggested comment without any additional comments, simply `Resolve` on GitHub will suffice.
There is no need to reply things like "Accepted", "Done", etc. as it just spams the reviewer's mailbox.

#### Can I resolve all comments in a single commit or each comment in an individual commit?

Review fixes should be pushed on separate commits for easier viewing on GitHub (unlike in e.g. Gerrit's amend-based flow).


## Release TODO list

1. Create release PR from `develop` into `master`.

1. Verify that all checks have passed.

1. Merge develop into master and push to remote repository using console (**not** using GitHub Merge Button):

         git checkout develop
         git pull origin develop
         git checkout master
         git pull origin master
         git merge --ff-only develop
         git push origin master

1. Verify that the release has been created on [GitHub](https://github.com/VirtusLab/git-machete/releases)
   and that a `git-machete-<VERSION>-1.noarch.rpm` file is present under the Assets.

1. Verify that the latest version is uploaded to [PyPI](https://pypi.org/project/git-machete).

1. Verify that the latest version is uploaded to [Anaconda](https://anaconda.org/conda-forge/git-machete).
   Thanks to the courtesy of [@asford (Alex Ford)](https://github.com/asford),
   there exists [conda-forge/git-machete-feedstock](https://github.com/conda-forge/git-machete-feedstock) repository.
   A bot is responsible for keeping the package up-to-date based on PyPI's release.
   Instruction on how to be a maintainer and other helpful tips can be found in
   [conda-forge recipe maintainer docs](https://conda-forge.org/docs/maintainer/adding_pkgs.html#recipe-maintainer).

1. Verify that there is an open PR in [homebrew-core](https://github.com/Homebrew/homebrew-core/pulls?q=is%3Apr+git-machete) titled: `git-machete <latest_version>`.

1. Verify that a Docker image for the new version has been pushed to Docker Hub: [gitmachete/git-machete](https://hub.docker.com/r/gitmachete/git-machete/tags).

1. Verify that a newly released version is present in `latest/stable` channel in [Snap](https://snapcraft.io/git-machete/releases).

   Install the `stable` revision locally (`sudo snap install --classic git-machete`)
   and verify that it works correctly, esp. if it comes to push/pull via ssh/https and editor (`git machete edit` and interactive rebases).

1. Verify that a build started for [docs at Read the Docs](https://readthedocs.org/projects/git-machete/builds/).
   If not, check `readthedocs.org` webhook on GitHub (under Settings > Webhooks).

   Once the build is ready, verify the [doc contents](https://git-machete.readthedocs.io/en/stable).

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

   If package-update PR has not been opened for a long time, it's probably due to the failure of Nix package build.
   Check [r-ryantm build system](https://r.ryantm.com/log/updatescript/git-machete/) for recent build logs.

1. Thanks to the courtesy of [Ila&iuml; Deutel](https://github.com/ilai-deutel),
   a [git-machete package](https://aur.archlinux.org/packages/git-machete) is hosted in Arch User Repository (AUR).
   If the release introduces significant changes/critical bugfixes, please [flag the package as out of date](https://aur.archlinux.org/pkgbase/git-machete/flag).

1. Verify that changes you made in files holding blogs content are reflected in the corresponding medium articles. Files and corresponding to them articles:
   * [blogs/git-machete-1/blog.md](https://github.com/VirtusLab/git-machete/blob/develop/blogs/git-machete-1/blog.md) &mdash; [Make your way through the git (rebase) jungle with Git Machete](https://medium.com/virtuslab/make-your-way-through-the-git-rebase-jungle-with-git-machete-e2ed4dbacd02);
   * [blogs/git-machete-2/blog.md](https://github.com/VirtusLab/git-machete/blob/develop/blogs/git-machete-2/blog.md) &mdash; [Git Machete Strikes again!](https://medium.com/virtuslab/git-machete-strikes-again-traverse-the-git-rebase-jungle-even-faster-with-v2-0-f43ebaf8abb0);
   * [blogs/docker-ci-tricks-1/blog.md](https://github.com/VirtusLab/git-machete/blob/develop/blogs/docker-ci-tricks-1/blog.md) &mdash; [Nifty Docker tricks for your CI (vol. 1)](https://medium.com/virtuslab/nifty-docker-tricks-for-your-ci-vol-1-c4a36d2192ea);
   * [blogs/docker-ci-tricks-2/blog.md](https://github.com/VirtusLab/git-machete/blob/develop/blogs/docker-ci-tricks-2/blog.md) &mdash; [Nifty Docker tricks for your CI (vol. 2)](https://medium.com/virtuslab/nifty-docker-tricks-for-your-ci-vol-2-c5191a67f1a4).

   If not, please apply changes on Medium to keep consistency.
   Since Medium does not offer conversion directly from Markdown, copy the formatted blog text from a GitHub and paste it into the Medium rich text editor.
   Once the changes are applied, make sure that the `<p>`/`<h1>` ids referenced from links
   in [README](README.md#reference) did not change (or are updated accordingly).
