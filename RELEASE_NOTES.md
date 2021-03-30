# Release notes

## New in git-machete 3.2.0

- added: `hub` command with `anno-prs`, `create-pr` and `retarget-pr` subcommands

## New in git-machete 3.1.0

- added: `--sync-github-prs`/`-H` and `--token` options to `anno`

## New in git-machete 3.0.0

- removed: support for Python 2
- removed: deprecated commands `infer` and `prune-branches`
- removed: standalone `format` command (`help format` can be used instead)

## New in git-machete 2.16.1

- fixed: PyPI deployment (ensure Travis uses Python 3.x)

## New in git-machete 2.16.0

- added: `squash` command

## New in git-machete 2.15.9

- fixed: Docker image used to open a PR to nixpkgs

## New in git-machete 2.15.8

- improved: both `master` (or `main`) and `develop` are automatically treated as roots in `discover`

## New in git-machete 2.15.7

- fixed: Reset to Remote and Fast Forward actions in our IntelliJ Plugin caused fork point to be inferred incorrectly
- added: CI also runs tests against Python 3.9 and latest version of Git

## New in git-machete 2.15.6

- fixed: `discover` crashing if neither of `develop` and `master` branches present and `--roots` not provided
- improved: consider `main` branch as a fixed root in discovery alongside `master` and `develop`

## New in git-machete 2.15.5

- changed: `develop` branch is taken as a fixed root in `discover` if `master` branch is missing

## New in git-machete 2.15.4

- improved: slide-out is suggested in certain contexts (like `status`) in case a non-existent branch is found in .git/machete

## New in git-machete 2.15.3

- changed: skip verification of managed branches for `anno` and `show`
- added: package for Ubuntu 20.04
- fixed: missing post-slide-out hook invocation after `advance`

## New in git-machete 2.15.2

- fixed: working directory in release scripts

## New in git-machete 2.15.1

- fixed: release process for Homebrew and NixOS/nixpkgs

## New in git-machete 2.15.0

- added: `addable` category of `list`
- added: `advance` command
- added: `machete-post-slide-out` hook
- added: support for `GIT_MACHETE_EDITOR` env var
- changed: `go root` no longer raises an error when the current branch is root
- fixed: `show root` no longer raises an error when the current branch is root
- fixed: Bash completion for `-y` option in several commands
- fixed: handling the case of current directory becoming non-existent (e.g. as a result of checkout)
- improved: `add` accepts remote branches as well (just like `git checkout`)
- improved: `discover` limited to ca. 10 most recently checked out branches by default
- improved: `discover` skips merged branches for which no child branches have been inferred
- improved: release process has been simplified

## New in git-machete 2.14.0

- added: `--as-root` option to `add`
- added: `--branch` option to `anno`
- added: `is-managed` plumbing command
- added: `current` subcommand to `show`
- added: animated gif to README + script for generating gifs automatically
- improved: formatting of help, prompts, logs, warnings and other messages
- fixed: help for a few existing commands

## New in git-machete 2.13.6

- fixed: remove reviewer setting when opening a PR to NixOS/nixpkgs
- changed: confinement of snaps from `strict` to `classic`
- changed: Docker images moved from under `virtuslab` organization to `gitmachete`
- changed: `apt-ppa` in all contexts to `deb-ppa`
- improved: determining the default editor (also including `git config core.editor`, `$GIT_EDITOR`, `editor` and `$VISUAL`)

## New in git-machete 2.13.5

- fixed: build of rpm package
- improved: organization of deployment stages on CI

## New in git-machete 2.13.4

- added: automatic opening of a PR to NixOS/nixpkgs on each release
- improved: `traverse` suggests to reset (`git reset --keep`) a local branch to its remote counterpart if the latter has newer commits
- fixed: handling corner cases when figuring out fork point

## New in git-machete 2.13.3

- fixed: minor release-related issues
- fixed: interactive input for `traverse` in case of an untracked branch

## New in git-machete 2.13.2

- added: support for Snappy
- added: script for creating an annotated tag for release
- added: extra checks in CI
- added: release guidelines
- fixed: implementation of backup of .git/machete file in `discover`

## New in git-machete 2.13.1

- fixed: deployment doesn't fail when `docker-compose push` fails for `rpm` or `apt-ppa-upload` services
- fixed: deployment condition for `rpm`

## New in git-machete 2.13.0

### Increased automation for `traverse` and other side-effecting commands

- added: `--yes` flag to `add`
- added: `--yes` flag to `delete-unmanaged`
- added: `--yes` flag to `discover`
- added: `--no-interactive-rebase` flag to `reapply`
- added: `--no-interactive-rebase` flag to `slide-out`
- added: `--fetch`, `--no-interactive-rebase`, `--return-to`, `--start-from`, `--whole`, `--yes` flags to `traverse`
- added: `--no-interactive-rebase` flag to `update`

### Manual fork point resolution

- added: fork point override feature via `--inferred`, `--override-to`, `--override-to-inferred`, `--override-to-parent` and `--unset-override` options of `fork-point`
- added: `with-overridden-fork-point` category of `list`

### Detection of an ongoing am session, cherry pick, merge, rebase or revert

- added: detection of an ongoing am session, cherry pick, merge, rebase or revert
- fixed: `traverse` used to continue the walk when interactive rebase stopped for `edit` (rather than stop the traversal and allow for the actual edits)

### Support for merge-based flows

- added: support for automated merging via `--merge` and `--no-edit-merge` flags of `slide-out`, `traverse` and `update`

### Other fixes & improvements

- added: `version` command
- fixed: in case the current branch is unmanaged, `go last` goes to the last branch under the *last* root and not to the last branch under the *first* root
- fixed: zsh completion for `add` and `s`
- improved: testing against multiple git versions in CI pipeline
- improved: functional tests invoke `discover` and `traverse`
- fixed: command-line argument validation for `list`
- added: `--list-commits-with-hashes` flag to `status`
- improved: stability of loading branch data from git
- fixed: predictability of handling branch remote tracking data
- fixed: fork point algorithm is now more resilient to corner cases in reflogs

## New in git-machete 2.12.10

- added: RPM package build
- fixed: Debian package no longer depends on `python3-pkg-resources`
- fixed: tests are no longer included in sdist tarball
- removed: support for building with make

## New in git-machete 2.12.9

- fixed: missing Debian build dependency on `git`
- fixed: issue with `brew install` (completion/ directory not being packaged into sdist)

## New in git-machete 2.12.8

- fixed: unpredictable behavior of `delete-unmanaged`
- fixed: build of Debian packages on PPA

## New in git-machete 2.12.7

- improved: logging output of external commands in `--debug` mode
- improved: simplified the sample `machete-status-branch` hook (no git submodules involved)
- improved: git-machete is compatible with git >= 2.0.0
- added: functional tests
- added: automatic push to brew tap repository
- added: automatic push to Ubuntu PPA

## New in git-machete 2.12.6

- fixed: trailing parts of the output of `git --version` are now removed

## New in git-machete 2.12.5

- improved: validation of generated Debian packages
- fixed: deployment to PyPI
- fixed: removed dependency on `distutils.spawn`

## New in git-machete 2.12.4

- fixed: remove stray ANSI escape characters in ASCII-only mode
- improved: `machete-status-branch` hook now receives `ASCII_ONLY` env var depending on whether `status` runs in ASCII-only mode
- fixed: artifact upload to Github Releases
- added: creation and upload of Debian packages to Github Releases

## New in git-machete 2.12.3

- improved: build process

## New in git-machete 2.12.2

- fixed: `discover --checked-out-since` was crashing for branches that weren't referenced anywhere in `git reflog HEAD`
- fixed: `discover --checked-out-since` was not taking some recently checked out branches into account
- fixed: branches could have been confused with identically named files by underlying `git reflog` invocations
- fixed: shellcheck has been applied on sample hook scripts
- improved: use `[y]es/[e]dit/[N]o` rather than `y[es]/e[dit]/N[o]` format in CLI prompts
- improved: underlying `git push` invocations are now using safer `--force-with-lease` rather than `--force`
- improved: log exit code, stdout and stderr of `machete-status-branch` hook in case exit code is non-zero

## New in git-machete 2.12.1

- fixed: remote tracking branches were not always properly updated during `traverse`

## New in git-machete 2.12.0

- added: `status` displays a message if there are no managed branches
- fixed: `edit` was crashing when both `EDITOR` variable and `vim` are missing
- fixed: remote tracking branch is now inferred for a local branch if it's not explicitly set
- fixed: only managed branches are now considered when inferring an upstream to add a branch onto
- added: `--checked-out-since` flag to `discover`
- improved: `go root`, `go first` and `go last` assume the first defined tree if the current branch is unmanaged

## New in git-machete 2.11.3

- improved: enabled installation via `pip install`

## New in git-machete 2.11.2

- fixed: choose fork point of B to its upstream U if B is descendant of U, but computed fork point is not a descendant of U

## New in git-machete 2.11.1

- fixed: wrong spacing in `status`

## New in git-machete 2.11.0

- added: `--color` flag to `status`

## New in git-machete 2.10.1

- changed: `file` displays absolute path

## New in git-machete 2.10.0

- changed: enable execution under both Python 2.7 and Python 3

## New in git-machete 2.9.0

- added: handling of `machete-pre-rebase` and `machete-status-branch` hooks + hook samples
- added: `yq` (yes-and-quit) choice in `traverse`
- added: `-r`/`--roots` option to `discover`
- improved: fork point commit is highlighted in `status --list-commits` in case of a yellow edge
- optimized: fetching state of the repository via git commands (esp. `config`, `for-each-ref`, `merge-base`, `reflog` and `rev-parse`)
- added: new edge color in `status` (grey) marks branches merged to their parents
- improved: suggest sliding out branches merged to their parents during `traverse`

## New in git-machete 2.8.8

- added: zsh completion

## New in git-machete 2.8.7

- changed: `%(refname:lstrip=2)` to `%(refname:strip=2)` in `git for-each-ref` format to make sure old versions of git work properly

## New in git-machete 2.8.6

- added: use project in python way and improve README

## New in git-machete 2.8.5

- fixed: fork point of a branch could be determined incorrectly when a no-op rebase has been performed on some other branch

## New in git-machete 2.8.4

- fixed: handle some extra cases happening when a tag named exactly as one of the managed branches exists in the repository

## New in git-machete 2.8.3

- improved: Bash completion for long options

## New in git-machete 2.8.2

- fixed: handle the cases when a tag named exactly as one of the managed branches exists in the repository

## New in git-machete 2.8.1

- fixed: handle the case when tracking information isn't set for a branch but the newly-chosen remote counterpart already exists (and thus a push with force or a pull might be needed)

## New in git-machete 2.8.0

- improved: for branches that are behind their upstream (merged to upstream), `traverse` suggests to slide them out instead of rebase onto that upstream

## New in git-machete 2.7.2

- fixed: location of bash completion script on Mac OS

## New in git-machete 2.7.1

- improved: visibility (esp. of yellow and grey elements) on white terminal backgrounds

## New in git-machete 2.7.0

- improved: during `traverse`, if there's a branch that's untracked, no longer rely on `git push` implicitly picking `origin` as the default remote

## New in git-machete 2.6.2

- improved: fork-point algorithm and upstream inference algorithm taking into account reflogs of remote counterparts of local branches
- fixed: a newline character is automatically added at the end of .git/machete file

## New in git-machete 2.6.1

- improved: simplified the upstream inference algorithm (now more aligned with the fork-point algorithm)

## New in git-machete 2.6.0

- added: `--debug` flag
- added: `delete-unmanaged` is the new name for `prune-branches` subcommand
- deprecated: `prune-branches` subcommand (retained for backward compatibility)
- added: ISSUE_TEMPLATE.md

## New in git-machete 2.5.5

- fixed: behavior of `discover` in a repository where no local branches exist (e.g. a newly-created one)

## New in git-machete 2.5.4

- improved: fetching the list of local branches

## New in git-machete 2.5.3

- fixed: upstream inference crashing for branches whose reflog is empty (due to e.g. expiry)

## New in git-machete 2.5.2

- added: link to the new blog post in README.md

## New in git-machete 2.5.1

- fixed: various issues with `help` subcommand, esp. when run for an alias

## New in git-machete 2.5.0

- added: `discover` is the new name for `infer` subcommand
- added: `l` is an alias for `log`
- deprecated: `infer` subcommand (retained for backward compatibility)
- improved: README

## New in git-machete 2.4.6

- improved: `infer` now works faster for large repositories

## New in git-machete 2.4.5

- fixed: corner cases in algorithm for computing fork point of a given branch

## New in git-machete 2.4.4

- fixed: `prune-branches` crashing when deleting a branch merged to HEAD but not to its remote tracking branch

## New in git-machete 2.4.3

- improved: `status` now works faster for large repositories

## New in git-machete 2.4.2

- updated: repository url in README.md
- removed: unused install.sh script

## New in git-machete 2.4.1

- fixed: use apostrophes instead of backticks in user-facing messages to comply with git's conventions

## New in git-machete 2.4.0

- improved: `show up`, `go up` and `update` use inferred parent branch if the current branch isn't managed

## New in git-machete 2.3.0

- added: `log` subcommand

## New in git-machete 2.2.0

- added: `first` and `last` params to `go` and `show` subcommands

## New in git-machete 2.1.2

- fixed: some initial `git` commands were skipped from logs when `--verbose` flag was passed
- fixed: faster validation of branches included in the definition file

## New in git-machete 2.1.1

- fixed: Makefile commands for install/uninstall

## New in git-machete 2.1.0

- added: `anno` subcommand

## New in git-machete 2.0.1

- fixed: `prune-branches` crashing when the currently checked-out branch was unmanaged

## New in git-machete 2.0.0

- added: `infer` subcommand
- added: `show` subcommand
- added: `list` subcommand has new category `slidable-after`
- improved: `add` subcommand behavior, including inference of desired upstream when possible
- improved: remote sync-ness information displayed by `status` (now corresponds to how git tracks remote counterparts)
- removed: `down`/`next`/`prev`/`root`/`up` subcommands
- removed: `-r`/`--remote` option to `status` and `traverse` subcommands

## New in git-machete 1.5.0

- improved: branch name completion in shell
- added: `list` subcommand (mostly for internal use of branch name completion)

## New in git-machete 1.4.0

- added: `traverse` subcommand that semi-automatically syncs the entire branch dependency tree

## New in git-machete 1.3.1

- added: extra checks for indent errors in the definition file

## New in git-machete 1.3.0

- added: custom annotations (e.g. PR number) allowed next to branch name in the definition file

## New in git-machete 1.2.0

- changed: allow to specify multiple branches when doing a `slide-out`

## New in git-machete 1.1.0

- changed: loosen requirements for `diff`, `fork-point` and `reapply` commands

## New in git-machete 1.0.2

- fixed: some `git machete` subcommands crashing when run from within a submodule

## New in git-machete 1.0.1

- fixed: some `git machete` subcommands crashing when run during an ongoing merge or rebase

