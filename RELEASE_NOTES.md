# Release notes

## New in git-machete 3.36.3

- added: release of git-machete snap to arm64 (requested by @jeff-scifin)

## New in git-machete 3.36.2

- improved: formatting of the output of `git machete ... --help` and `git machete help ...`
- fixed: `git machete -v` (no command) crashing
- fixed: leading and trailing whitespace is now ignored in all interactive input

## New in git-machete 3.36.1

- fixed: incorrect `Could not determine base branch for PR` error messages when creating PRs from `git machete traverse -H`
- fixed: `git bisect` is recognized as a separate repository state by `git machete status` and side-effecting operations
- fixed: branches marked as `slide-out=no` are no longer slid out by `git machete slide-out --removed-from-remote`
- fixed: if current branch hasn't been slid out, then `git machete slide-out` no longer switches the current branch

## New in git-machete 3.36.0

- deprecated: `git machete fork-point --override-to=...` and `--override-to-inferred` options; use `--override-to-parent`, or run `git machete update [--fork-point=...]` instead

## New in git-machete 3.35.1

- fixed: `git machete git{hub,lab} update-{pr,mr}-descriptions --related` could not update the current PR/MR in default intro style

## New in git-machete 3.35.0

- added: `git machete traverse --sync-github-prs`/`--sync-gitlab-mrs` suggests creating PRs/MRs for branches without one (suggested by @bradneuman and @tir38)

## New in git-machete 3.34.1

- fixed: `yq` answer to retargeting a PR/MR in `traverse` was treated just as `y`/`yes` (no quitting)

## New in git-machete 3.34.0

- added: new `full-no-branches` and `up-only-no-branches` values to `machete.github.prDescriptionIntroStyle` and `machete.gitlab.mrDescriptionIntroStyle` git config keys
- fixed: preserve trailing lines when updating PR/MR descriptions
- fixed: generated sections of GitLab MRs include MR titles (as in GitHub PRs)

## New in git-machete 3.33.0

- added: `--by=...` flag to `git machete git{hub,lab} update-{pr,mr}-descriptions`

## New in git-machete 3.32.1

- fixed: `git machete github` and `gitlab` recognize SSH URLs with any user before `@`, not just `git`

## New in git-machete 3.32.0

- added: flags `-H`/`--sync-github-prs` and `-L`/`--sync-gitlab-mrs` to `traverse` to suggest retargeting PRs/MRs when traversing (suggested by @chriscz)
- removed: no longer release new packages to Ubuntu PPA

## New in git-machete 3.31.1

- fixed: AUR package installation (reported by @jan-san)

## New in git-machete 3.31.0

- added: `git machete git{hub,lab} update-{pr,mr}-descriptions` subcommands
- added: `git machete git{hub,lab} create-{pr,mr} --update-related-descriptions` flags
- added: `git machete git{hub,lab} restack-{pr,mr} --update-related-descriptions` flags
- added: `git machete git{hub,lab} retarget-{pr,mr} --update-related-descriptions` flags
- added: `machete.traverse.fetch.<remote>` git config key to selectively exclude remotes from `git machete traverse --fetch` (contributed by @gjulianm)

## New in git-machete 3.30.0

- added: support for Python 3.13 (earlier versions of git-machete should also work on Python 3.13 outside certain rare cases when in `--debug` mode)

## New in git-machete 3.29.3

- changed: no longer publish RPM files with GitHub releases
- fixed: work around the parsing bug in `git patch-id` v2.46.1 (reported by @ilai-deutel)
- fixed: `git machete git{hub,lab} create-{pr,mr}` takes into account `<!-- {start,end} git-machete generated -->` in PR/MR template (suggested by @frank-west-iii)

## New in git-machete 3.29.2

- changed: no longer publish Docker images

## New in git-machete 3.29.1

- improved: `git-machete delete-unmanaged` uses the same algorithm as `status` and `traverse` to recognize merged branches (suggested by @cinnamennen)

## New in git-machete 3.29.0

- added: git config keys `machete.github.prDescriptionIntroStyle` and `machete.gitlab.mrDescriptionIntroStyle`
- added: ability to turn off PR/MR description intro completely by setting the git config key to `none` (suggested by @tir38)
- added: ability to include downstream PRs/MRs in PR/MR description intro by setting the git config key to `full` (suggested by @aouaki)
- changed: layout and ordering of PRs/MRs in PR/MR description intro to better match `git machete status`

## New in git-machete 3.28.0

- added: ability to specify pass-through flags in `diff` and `log`, for example `git machete diff -- file.txt`, `git machete log -- --patch` (partly contributed by @tdyas)

## New in git-machete 3.27.0

- added: git config key `http.sslVerify` is honored when connecting to GitHub and GitLab APIs (suggested by @scamden)

## New in git-machete 3.26.4

- fixed: avoid detecting a cycle when there's a PR/MR from `main` or `master` in a fork to the original repo (reported by @Joibel)
- fixed: `git machete git{hub,lab} create-{pr,mr}` no longer fails when creating a PR/MR across forks; instead, a forked PR is created (reported by @cspotcode)
- improved: `git machete git{hub,lab} checkout-{prs,mrs}` only adds annotations to affected branches (and not to every branch)

## New in git-machete 3.26.3

- improved: performance of listing commits for red-edge branches on large repos
- improved: message in case of missing `.git/machete` file suggests to use `git machete git{hub,lab} checkout-{prs,mrs}`
- fixed: pass `-c log.showSignature=false` to all `git` invocations to hide GPG signatures in logs; if `log.showSignature` were set to a value equivalent to `true` in a user's `git` configuration, the GPG signatures shown in logs would cause errors in `git log` and `git reflog` parsing internal to `git machete` (reported and contributed by @goxberry)

## New in git-machete 3.26.2

- fixed: parsing of multiline git config keys (reported by @saveman71)

## New in git-machete 3.26.1

- fixed: readability of autogenerated PR/MR descriptions
- improved: `git machete github restack-pr` and `git machete gitlab restack-mr` fail on branches marked as `push=no`, instead of printing a warning and proceeding with retargeting anyway

## New in git-machete 3.26.0

- added: better detection of squash merges and rebases, controlled by flag `--squash-merge-detection={none,simple,exact}` (`status` and `traverse`) and git config key `machete.squashMergeDetection` (contributed by @gjulianm)
- deprecated: `--no-detect-squash-merges` flag in `status` and `traverse` &mdash; use `--squash-merge-detection=none` instead (contributed by @gjulianm)

## New in git-machete 3.25.3

- fixed: `-y` option in `git machete traverse` automatically sets `--no-edit-merge` flag, to retain behavior when the `update=merge` qualifier is set (contributed by @gjulianm)
- fixed: `push=no` and `slide-out=no` qualifiers now work in `git machete advance` now
- fixed: `rebase=no` qualifier now works in `git machete slide-out`
- improved: in `git machete github create-pr`/`gitlab create-mr`, check whether base/target branch for PR/MR exists in remote, instead of fetching the entire remote

## New in git-machete 3.25.2

- fixed: Homebrew deploys

## New in git-machete 3.25.1

- fixed: `git machete git{hub,lab} restack-{pr,mr}` now first retargets, then pushes (so that certain CIs see the correct base branch in env vars)

## New in git-machete 3.25.0

- added: GitLab support via `git machete gitlab` (first suggested by @mikeynap, partly contributed by @max-nicholson)
- added: `git machete anno -L`/`--sync-gitlab-mrs` flag
- fixed: checking out GitHub PRs where head branch comes from an already deleted fork
- added: qualifier `update=merge` allows selecting merge strategy per branch (contributed by @gjulianm)
- added: Scoop package for Windows (suggested by @ppasieka)

## New in git-machete 3.24.2

- fixed: automatic updates of Homebrew formula

## New in git-machete 3.24.1

- fixed: deployment issues

## New in git-machete 3.24.0

- added: `-f`/`--as-first-child` flag to `git machete add` (contributed by @matthalp)
- fixed: `git machete github retarget-pr` not updating description of PR due to stray `\r` characters

## New in git-machete 3.23.2

- fixed: make fork-point also take into account common ancestors (and not only reflogs) in more cases

## New in git-machete 3.23.1

- fixed: if a PR has a pre-v3.23.0 `Based on PR #...` header, then it's removed by `git machete github retarget-pr` in favor of the new extended PR chain

## New in git-machete 3.23.0

- added: full chain of PRs (and not just a link to the base PR) is added to/updated in PR description by `git machete github create-pr`/`retarget-pr`/`restack-pr` (suggested by @mjgigli)
- fixed: in the unlikely case of a cycle between GitHub PRs, `git machete github checkout-pr` aborts with an error rather than falling into an infinite loop
- fixed: when checking out longer PR chains, `git machete github checkout-prs` prints out all checked out branches correctly

## New in git-machete 3.22.0

- improved: if neither `.git/info/description` nor `.github/pull_request_template.md` is present, `git machete github create-pr` now uses message body of the first unique commit as PR description (suggested by @kamaradclimber)
- added: `machete.github.forceDescriptionFromCommitMessage` git config key that forces `git machete github create-pr` to use message body of the first unique commit as PR description (suggested by @kamaradclimber)

## New in git-machete 3.21.1

- fixed: `Cannot parse Link header` error in `git machete github` subcommands when there are more than 100 PRs in the given repository (reported by @domesticsimian)
- fixed: if `.git/machete` doesn't exist, `git machete add <branch>` adds both current branch and the newly-added `<branch>` (not just the latter)

## New in git-machete 3.21.0

- added: `--removed-from-remote` flag to `git machete slide-out` (contributed by @raylu)
- added: `--title` flag to `git machete github create-pr` that allows for setting PR title explicitly (suggested by @mjgigli)
- added: `--with-urls` flag to `git machete github anno-prs` and `machete.github.annotateWithUrls` git config key that allow for adding the URL of the PR to the annotations (contributed by @guyboltonking)
- added: `--yes` flag to `git machete github create-pr` so that the user isn't asked whether to push the branch (suggested by @mkondratek)
- deprecated: `git machete clean` and `git machete github sync`; use `github checkout-prs --mine`, `delete-unmanaged` and `slide-out --removed-from-remote` instead
- fixed: PR author is now always added to annotation if different from current user (contributed by @guyboltonking)

## New in git-machete 3.20.0

- added: `git machete github create-pr` adds a comment linking the PR to its base PR; `github retarget-pr` keeps that comment up to date (suggested by @guyboltonking)
- added: new subcommand `git machete github restack-pr`, which (force-)pushes and retargets the PR, without adding code owners as reviewers in the process (suggested by @raylu)
- improved: when running `git machete squash` against a root branch, the error message suggests using `--fork-point=...` flag (suggested by @levinotik)
- improved: simplified & clarified docs in multiple places (partly suggested by @kgadek)

## New in git-machete 3.19.0

- added: support for Python 3.12
- improved: `git machete github create-pr` also checks for `.github/pull_request_template.md` for description (contributed by @raylu)

## New in git-machete 3.18.3

- added: arm64 packages in Ubuntu PPA

## New in git-machete 3.18.2

- fixed: reading tokens from `~/.github-token` for GitHub Enterprise domains (reported by @mkondratek)
- fixed: `git machete github retarget-pr`, when invoked without `--ignore-if-missing`, actually fails now if there is no PR for the branch
- improved: GitHub tokens are automatically redacted from command outputs in `--debug` mode

## New in git-machete 3.18.1

- fixed: `machete.github.remote` git config key can be specified independently from `machete.github.organization` and `machete.github.repository`

## New in git-machete 3.18.0

- added: `git machete completion bash|fish|zsh` command
- fixed: multiple glitches in the existing bash/fish/zsh completions

## New in git-machete 3.17.9

- improved: layout of documentation at ReadTheDocs
- improved: replaced `definition file` with `branch layout file` across the docs

## New in git-machete 3.17.8

- fixed: building the package for Ubuntu PPA

## New in git-machete 3.17.7

- fixed: `fish` completion no longer prompts file names alongside commands/flags (contributed by @guyboltonking)

## New in git-machete 3.17.6

- fixed: `git machete github` not being able to retrieve token used by `gh` for `gh` version >= 2.31.0 (reported by @domesticsimian)

## New in git-machete 3.17.5

- fixed: `machete-post-slide-out`, `machete-pre-rebase` and `machete-status-branch` hooks can now be executed on Windows
- fixed: unstable behavior after `edit` option has been selected for interactively sliding out invalid branches
- fixed: handling of HTTP redirects when `git machete github create-pr` and `retarget-pr` act on a repository that has been renamed and/or moved
- improved: `git machete github retarget-pr` now fails if there are multiple PR with the given head branch (rather than silently take the first of them into account)

## New in git-machete 3.17.4

- fixed: building the docs for readthedocs.org
- fixed: building the package for Arch User Repository (reported by @chrislea)
- fixed: `.git/rebase-merge/author-script` used to be rewritten to CRLF newlines on Windows, breaking the rebases (reported by @cspotcode)

## New in git-machete 3.17.3

- fixed: building the package for Alpine Linux (contributed by @Ikke)

## New in git-machete 3.17.2

- fixed: when `origin/feature/foo` branch exists, `git machete add foo` no longer falsely recognizes `origin/feature/foo` as a potential remote tracking branch for `foo`
- fixed: on Windows, git-machete installed globally via `pip` no longer crashes on `ModuleNotFoundError` within venvs (contributed by @cspotcode)

## New in git-machete 3.17.1

- fixed: in the rare case when overridden fork point for branch X is an ancestor of X's parent, the effective fork point is selected to the latest common ancestor of X and X's parent
- improved: if git >= 2.30.0, pass `--force-if-includes` to `git push` alongside `--force-with-lease`

## New in git-machete 3.17.0

- added: `--ignore-if-missing` flag to `git machete github retarget-pr` command
- added: `--branch=<branch>` option to `git machete github retarget-pr` command
- fixed: `github anno-prs` no longer assumes that local branch and its remote counterpart share the same name
- fixed: `git machete --help` displays a man page (instead of crashing with `No manual entry for git-machete`) when git-machete is installed via Homebrew

## New in git-machete 3.16.3

- fixed: a few glitches in the animated gif in README

## New in git-machete 3.16.2

- fixed: interactive rebase triggered by `traverse`, `update` etc. no longer fails when an effectively-empty commit (commit whose changes have already been applied in the given rebase) is encountered

## New in git-machete 3.16.1

- fixed: `advance` crashing when the current branch is untracked

## New in git-machete 3.16.0

- deprecated: `machete.overrideForkPoint.<branch>.whileDescendantOf` is no longer taken into account; it's still written, however, for compatibility reasons

## New in git-machete 3.15.2

- fixed: zsh shell completion for the `slide-out` command no longer fails
- fixed: GitHub token retrieval logic

## New in git-machete 3.15.1

- fixed: in case of red edge, the unique history of a branch never includes commits reachable from its parent

## New in git-machete 3.15.0

- improved: formatting in `git machete` command prompts and outputs
- added: `slide-out=no` branch qualifier that controls the slide-out behaviour of `git machete traverse`

## New in git-machete 3.14.3

- improved: docs for `machete.github.*` and other config keys

## New in git-machete 3.14.2

- fixed: superfluous whitespace around fork point hint in `status`

## New in git-machete 3.14.1

- fixed: URL prefix for GitHub Enterprise API endpoints

## New in git-machete 3.14.0

- added: `push=no` and `rebase=no` branch qualifiers that control push and rebase behaviour of `git machete traverse`
- added: `machete.github.domain` config key to support GitHub Enterprise domains
- added: support for per-domain entries in `~/.github-token` file
- fixed: fetching GitHub PRs when there is more than 30 of them in the given repository
- fixed: shell completions suggest `t` (alias for `traverse`) as a valid command

## New in git-machete 3.13.2

- fixed: redo the failed release

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
