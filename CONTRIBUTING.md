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

Install `fish` and `shellcheck` for `run-all-checks.sh` to pass successfully.

## Run tests locally

```shell
tox -e py
```

To display rich diff when tests fail, use
```shell
tox -e py -- -k github -vv  # also, use -k for tests whose names contain a specific string
```

To display full operands in failed assertions (rather than just diffs), use
```shell
tox -e py -- -k "hub or lab" --full-operands  # logical expressions are also allowed in -k
```

## Install locally for development purposes

### Terminal: venv

To execute `git-machete` commands in terminal using current branch implementation, you must first have a virtual environment.
You can create one named `venv` by executing `tox -e venv` or use existing environment (need to install requirements from [requirements/testenv.txt](requirements/testenv.txt)).
You have to activate the environment, for the `venv` environment run `source .tox/venv/bin/activate` from `git-machete` root directory.
Lastly, install `git-machete` in development mode with `pip install --editable .` --- codebase can now be edited in-place without reinstallation.

### Terminal: user-wide installation

Use `pip install --user .`. Locate the installed package with `pip show -f git-machete` --- you'll see something like:

```
<...metadata...>
Location: /Users/pawel_lipski/Library/Python/3.9/lib/python/site-packages
Requires:
Required-by:
Files:
  <...files...>
  ../../../bin/git-machete
  <...files...>
```

Compound the `Location` with the relative path to `bin/git-machete` launcher script to locate the directory where the launcher script is located.
In the above macOS example, it'll be `$HOME/Library/Python/3.9/bin`.
On Linuxes, it's likely to be `$HOME/.local/bin` instead.
Add this directory to `PATH`.
Re-installation will be needed after a modification, as `--editable` and `--user` don't seem to work together.

### IDE (PyCharm): venv

To execute tests in IDE (e.g. PyCharm -> right-clicking on the test file or clicking the green triangle on the left of the test case name),
you must first have a virtual environment. You can create one named `venv` by executing `tox -e venv` or use existing environment
(but then you need to install requirements from [requirements/testenv.txt](requirements/testenv.txt)).
Lastly, setup `python` interpreter for your project in the IDE, e.g. `.tox/venv/bin/python`.

To run/debug `git-machete` commands directly in IDE you need to create custom *Run/Debug Configuration*: set *Script Path* e.g. to [`git_machete/cli.py`](git_machete/cli.py)
and provide command as *Parameters*.


## Generate sandbox repositories

Run [`graphics/setup-sandbox`](graphics/setup-sandbox) script to set up a test repo under `~/machete-sandbox` with a remote in `~/machete-sandbox-remote`.


## Regenerate the GIF in README.md

1. Install [asciinema](https://github.com/asciinema/asciinema),
   [agg (at least v1.4.1)](https://github.com/asciinema/agg),
   and [sponge](https://linux.die.net/man/1/sponge).
   On macOS, just `brew install asciinema agg sponge` should be enough.
1. Run [`./graphics/generate-asciinema-gif graphics/discover-status-traverse.gif`](graphics/generate-asciinema-gif).


## Command properties/classification

Deprecated commands are excluded.

| Property                                                          | Commands                                                                                                                                           |
|-------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|
| can accept interactive input on stdin                             | `add`, `advance`, `delete-unmanaged`, `discover`, `github`<sup>[1]</sup>, `gitlab`<sup>[1]</sup>, `go`, `traverse`, `update`                       |
| can display status (and run `machete-status-branch` hook)         | `discover`, `github`<sup>[1]</sup>, `gitlab`<sup>[1]</sup>, `status`, `traverse`                                                                   |
| can modify the .git/machete file                                  | `add`, `advance`, `anno`, `discover`, `edit`, `github`, `gitlab`, `slide-out`, `traverse`                                                          |
| can modify the git repository (excluding .git/machete)            | `add`, `advance`, `delete-unmanaged`, `github`<sup>[1]</sup>, `gitlab`<sup>[1]</sup>, `go`, `reapply`, `slide-out`, `squash`, `traverse`, `update` |
| can run merge                                                     | `advance`<sup>[2]</sup>, `slide-out`, `traverse`, `update`                                                                                         |
| can run rebase (and run `machete-pre-rebase` hook)                | `reapply`<sup>[3]</sup>, `slide-out`, `traverse`, `update`                                                                                         |
| can slide out a branch (and run `machete-post-slide-out` hook)    | `advance`, `slide-out`, `traverse`                                                                                                                 |
| expects no ongoing rebase/merge/cherry-pick/revert/am             | `advance`, `go`, `reapply`, `slide-out`, `squash`, `traverse`, `update`                                                                            |
| has stable output format across minor versions (plumbing command) | `file`, `fork-point`<sup>[4]</sup>, `is-managed`, `list`, `show`, `version`                                                                        |

[1]: `github`/`gitlab` can only display status, accept interactive mode or modify git repository when `create-{pr,mr}`, `checkout-{pr,mr}s` or `restack-{pr,mr}` subcommand is executed.

[2]: `advance` can only run fast-forward merge (`git merge --ff-only`).

[3]: `reapply` can run rebase but can't run merge since merging a branch with its own fork point is a no-op and generally doesn't make much sense.

[4]: A stable output is only guaranteed for `fork-point` when invoked without any option or only with `--inferred` option.


## Versioning

This tool is [semantically versioned](https://semver.org) with respect to all of the following:

* Python and Git version compatibility
* command-line interface (commands and their options)
* format of its specific files (like `.git/machete` but also e.g. `.git/info/description` and `~/.github-token`)
* hooks and their command-line interface
* output format of [plumbing commands](#command-propertiesclassification)
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

1. Verify that changes you made in files holding blogs content (if any) are reflected in the corresponding medium articles:
   * [blogs/git-machete-1/blog.md](https://github.com/VirtusLab/git-machete/blob/develop/blogs/git-machete-1/blog.md) &mdash; [Make your way through the git (rebase) jungle with Git Machete](https://medium.com/virtuslab/make-your-way-through-the-git-rebase-jungle-with-git-machete-e2ed4dbacd02);
   * [blogs/git-machete-2/blog.md](https://github.com/VirtusLab/git-machete/blob/develop/blogs/git-machete-2/blog.md) &mdash; [Git Machete Strikes again!](https://medium.com/virtuslab/git-machete-strikes-again-traverse-the-git-rebase-jungle-even-faster-with-v2-0-f43ebaf8abb0);
   * [blogs/docker-ci-tricks-1/blog.md](https://github.com/VirtusLab/git-machete/blob/develop/blogs/docker-ci-tricks-1/blog.md) &mdash; [Nifty Docker tricks for your CI (vol. 1)](https://medium.com/virtuslab/nifty-docker-tricks-for-your-ci-vol-1-c4a36d2192ea);
   * [blogs/docker-ci-tricks-2/blog.md](https://github.com/VirtusLab/git-machete/blob/develop/blogs/docker-ci-tricks-2/blog.md) &mdash; [Nifty Docker tricks for your CI (vol. 2)](https://medium.com/virtuslab/nifty-docker-tricks-for-your-ci-vol-2-c5191a67f1a4).

   If not, please apply changes on Medium to keep consistency.
   Since Medium does not offer conversion directly from Markdown, copy the formatted blog text from a GitHub and paste it into the Medium rich text editor.
   Once the changes are applied, make sure that the `<p>`/`<h1>` ids referenced from links
   in [README](README.md#reference) did not change (or are updated accordingly).
