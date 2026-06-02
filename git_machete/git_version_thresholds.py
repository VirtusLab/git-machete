from typing import Tuple

GitVersion = Tuple[int, int, int]

# Centralized catalog of the `git` version thresholds that matter for git-machete's behavior.
#
# Each constant marks the *earliest* `git` version at (or from) which a given CLI feature/flag exists
# or a given upstream bug is fixed (the lone exception is `PATCH_ID_UNSTABLE_OUTPUT_ORDER`, which marks
# a single buggy version - see its comment).
# Keeping them here (rather than as bare `(2, 5)`-style tuples sprinkled across `git_machete/` and `tests/`)
# means the "why this number" rationale lives in exactly one place, and a bump only has to happen once.
#
# A couple of these constants are not consumed by any runtime version check; they exist purely to document a
# compatibility boundary that the code relies on implicitly (the minimum supported version, and the version below
# which a config-parameter workaround is needed instead of a CLI flag). Such constants are marked with
# `# noqa: F841` so the unused-name linters don't flag them - they're documentation, not dead code.

# Minimum `git` version git-machete declares support for (see the "Git compatibility" section of README.md;
# exercised in CI via the oldest image in .circleci/config.yml).
# git-machete has advertised compatibility with `git >= 1.8.0` since git-machete 2.13.0 (it was `>= 2.0.0` before that).
# The floor is `git branch --set-upstream-to` (used unconditionally in git.py's `set_upstream_to`): that flag was
# introduced in git 1.8.0 - alongside the deprecation of the reversed-argument `git branch --set-upstream` - and
# git-machete carries no fallback for older git, so 1.8.0 is a hard feature boundary.
MINIMUM_SUPPORTED_GIT_VERSION: GitVersion = (1, 8, 0)  # noqa: F841

# Earliest version to support `git push --force-with-lease`.
PUSH_FORCE_WITH_LEASE: GitVersion = (1, 8, 5)

# `git worktree` command was introduced here; below this version git-machete degrades to treating the
# current checkout as the only worktree.
WORKTREE_COMMAND: GitVersion = (2, 5, 0)

# `log.showSignature` config setting (and the `--no-show-signature` flag) do not exist before this version.
# We suppress GPG signatures in `git log` output by passing `-c log.showSignature=false` rather than the flag,
# precisely so that we stay compatible with pre-2.10.0 `git` (which silently ignores an unknown `-c` setting).
# See the `GIT_EXEC` definition in git_machete/git.py and GitHub issue #1286.
LOG_SHOW_SIGNATURE_CONFIG: GitVersion = (2, 10, 0)  # noqa: F841

# This version fixed a bug that made fetching the reflog of more than one branch at a time unreliable.
# At/above it we batch-load all reflogs in one go; below it we fetch each branch's reflog separately.
RELIABLE_MULTI_BRANCH_REFLOG: GitVersion = (2, 14, 2)

# `git worktree remove` was introduced here; below this version git-machete removes a linked worktree
# by hand (`rmtree` + `git worktree prune`).
WORKTREE_REMOVE_COMMAND: GitVersion = (2, 17, 0)

# Earliest version to accept `git rebase --empty=drop` (the flag git-machete passes so that
# interactive rebases drop commits that became empty, matching the non-interactive default).
REBASE_EMPTY_DROP: GitVersion = (2, 26, 0)

# Earliest version to support `git push --force-with-lease --force-if-includes`.
PUSH_FORCE_IF_INCLUDES: GitVersion = (2, 30, 0)

# As of this version `git` itself keeps the process's CWD valid when the underlying checkout removes it,
# so git-machete's own "current directory no longer exists" fallback (in git_machete/cli.py) is only needed
# to defend against older `git`.
# See https://github.com/git/git/blob/master/Documentation/RelNotes/2.35.0.txt#L81
CWD_REMOVAL_HANDLED_BY_GIT: GitVersion = (2, 35, 0)

# This *single* version of `git patch-id` emits its output in a different order than every neighboring version
# (the bug exists in 2.46.1 but not in <=2.46.0 or >=2.46.2), so it needs a dedicated code path that pairs each
# patch-id with the right commit hash. See GitHub issue #1329.
PATCH_ID_UNSTABLE_OUTPUT_ORDER: GitVersion = (2, 46, 1)
