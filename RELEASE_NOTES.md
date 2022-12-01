# Release notes

## New in git-machete 3.13.1

- fixed: support GitHub remote URLs without `.git` suffix
- fixed: `git machete` now correctly displays only available commands (without help topics)
- fixed: `git machete traverse -y -M` no longer exits with error
- fixed: `git machete` commands no longer exit with stack trace when interrupted by Ctrl+C

## New in git-machete 3.13.0

- improved: modify formatting of command line documentation
- added: `git machete help <command>` now accepts command aliases
- fixed: removed stack trace when terminating `git machete` command prompt with `Ctrl+D`
- added: support for Python 3.11
- added: machete config key `machete.traverse.push` that controls default behavior of `traverse` command
- improved: formatting of the `config` section in the sphinx documentation

## New in git-machete 3.12.5

- added: `git machete github retarget-pr` now updates annotation for the branch associated with the retargeted PR
- improved: modify formatting in error message for `github create-pr`
- fixed: modify formatting of `git machete` commands output
- improved: the .gif file in the README.md file has been slowed down to provide a better viewing experience

## New in git-machete 3.12.4

- fixed: Homebrew release process

## New in git-machete 3.12.3

- fixed: release instructions in CONTRIBUTING.md are now correct
- fixed: release to Homebrew doesn't crash the deployment process

## New in git-machete 3.12.2

- added: `git-machete` is now available in homebrew core formulae; if `git-machete` has already been installed from the tap on a given machine, `brew` should automatically pull new updates from homebrew core from now on
- fixed: fork-point overridden with commit hash that no longer exists is ignored (doesn't crash git-machete anymore)

## New in git-machete 3.12.1

- fixed: removed redundant files from Ubuntu package
- fixed: fork-point overridden with invalid commit hash is ignored (doesn't crash git-machete anymore)
- fixed: `git machete diff` now works as intended (runs `git diff` against the current working directory, not the current branch)

## New in git-machete 3.12.0

- added: subcommand `git machete list childless`

## New in git-machete 3.11.6

- added: package for Ubuntu 22.04 LTS
- fixed: spurious failures in the build of Debian packages

## New in git-machete 3.11.5

- fixed: `git machete edit` accepts arguments (and not only executable path/name) in the editor pointed by git config or environment variable

## New in git-machete 3.11.4

- fixed: git-machete crashing when a local branch uses another local branch as its remote tracking branch (`git config branch.BRANCH.remote` set to `.`)
- fixed: fork point incorrectly inferred when a branch has been pushed immediately after being created
- fixed: output of `help` no longer includes ANSI escape codes when stdout is not a terminal
- fixed: all newlines are skipped from the output of `machete-status-branch` hook to avoid messing up the rendered status

## New in git-machete 3.11.3

- added: support GitHub remote URL in the form of `https://USERNAME@github.com/ORGANIZATION/REPOSITORY.git`

## New in git-machete 3.11.2

- fixed: `git machete` now correctly infers remote for fetching of branch when the branch is associated with more than one remote
- fixed: `git machete github create-pr` and `retarget-pr` now take branch tracking data into account when finding out where (in what GitHub organization/repository) to create a PR

## New in git-machete 3.11.1

- fixed: release to Snap Store

## New in git-machete 3.11.0

- added: `git machete help config` help topic and sphinx documentation page for config keys and environment variables
- added: boolean git config key `machete.worktree.useTopLevelMacheteFile` for switching the machete file location for worktrees: a single central `.git/machete` for all worktrees (as up to 3.10) or a per-worktree `.git/worktrees/.../machete`
- added: when GitHub token is invalid/expired, provide information which token provider has been used

## New in git-machete 3.10.1

- added: support GitHub remote URL in the form of `ssh://git@github.com/USERNAME/REPOSITORY.git`
- fixed: `git machete diff` doesn't crash when supplied with a short branch name (e.g. `develop`)
- fixed: `git machete {add, anno, diff, fork-point, is-managed, log, show}` don't crash when supplied with a full branch name (e.g. `refs/heads/develop`)

## New in git-machete 3.10.0

- added: boolean git config key `machete.status.extraSpaceBeforeBranchName` that enable configurable rendering of `status` command
- added: 3 git config keys `machete.github.{remote,organization,repository}` that enable `git machete github *` subcommands to work with custom GitHub URLs

## New in git-machete 3.9.1

- fixed: better rendering of edge junctions in `status`

## New in git-machete 3.9.0

- added: `advance` command now also pushes the branch after the merge
- fixed: `fork-point` no longer specially treats branches merged to its parent
- fixed: color scheme on 8-color terminals

## New in git-machete 3.8.0

- added: `--all`, `--mine`, `--by` flags and parameter `<PR-number-1> ... <PR-number-N>` to `git machete github checkout-prs`
- fixed: cherry-pick/merge/rebase/revert is detected on a per-worktree basis
- added: command `git machete clean` with `--checkout-my-github-prs` flag and its equivalent `git machete github sync`
- added: `--delete` flag to `git machete slide-out` command for deleting slid-out branches from git

## New in git-machete 3.7.2

- fixed: package version retrieval outside of git repository
- fixed: checking whether a branch is merged to parent works for branches that have no common commit
- added: CI/CD check ensuring that RELEASE_NOTES are up to date
- fixed: `github create-pr` takes the PR title from the first unique commit

## New in git-machete 3.7.1

- fixed: build process of Docker images

## New in git-machete 3.7.0

- added: extra options can be passed to the underlying `git rebase` via `GIT_MACHETE_REBASE_OPTS` env var (suggested by @kgadek)

## New in git-machete 3.6.2

- added: `gitmachete/git-machete` Docker image (contributed by @mohitsaxenaknoldus)
- fixed: build process stability

## New in git-machete 3.6.1

- fixed: support for worktrees (reported by @kgadek)

## New in git-machete 3.6.0

- added: `t` alias for `traverse` command
- fixed: remove underscore from `--start-from` flag for `traverse` subcommand

## New in git-machete 3.5.0

- added: new way of acquiring the github token (from `~/.github-token`)
- fixed: `--fork-point` and `--down-fork-point` options values have to be ancestor of the current branch
- added: fish shell completions (contributed by @kgadek)

## New in git-machete 3.4.1

- fixed: wrong logo path in Snapcraft config

## New in git-machete 3.4.0

- added: `github` command with `anno-prs`, `checkout-prs`, `create-pr` and `retarget-pr` subcommands
- added: documentation on readthedocs.io
- fixed: documentation displayed with `help`/`-h`/`--help`
- improved: content of git-machete project related blogs has been moved to this repo and updated
- removed: releases to Nixpkgs no longer happen directly from our CI pipeline

## New in git-machete 3.3.0

- improved: `show` can accept a target branch other than the current branch (contributed by @asford)
- added: `--no-push`, `--no-push-remote`, `--push` and `--push-untracked` flags in `traverse` to optionally skip pushing to remote (contributed by @asford)

## New in git-machete 3.2.1

- fixed: newly created branches were sometimes incorrectly recognized as merged to parent
- improved: GitHub API token is resolved from `gh` or `hub` if available

## New in git-machete 3.2.0

- improved: `slide-out` can target branches with any number of downstream (child) branches (contributed by @asford)
- fixed: detection of no-op rebase cases in fork-point algorithm
- fixed: if a branch is merged to its parent, `git machete status -l` now always displays an empty list of commits
- improved: `status` and `traverse` by default also consider squash merges when checking if a branch is merged to parent (contributed by @asford)
- added: `--no-detect-squash-merges` flag in `status` and `traverse` to fall back to strict merge detection

## New in git-machete 3.1.1

- fixed: `add` without `--onto` crashing when the current branch is not managed
- fixed: commit message and PR description for `NixOS/nixpkgs`

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
- fixed: artifact upload to GitHub Releases
- added: creation and upload of Debian packages to GitHub Releases

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
