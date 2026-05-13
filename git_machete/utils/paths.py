"""POSIX-style typed paths and helpers.

Every `Path` / `AbsPath` instance is normalised to forward-slash form on
construction (via `PurePath(value).as_posix()`), regardless of platform.
This is load-bearing for:

* path equality / dictionary membership (`current_worktree_root_dir ==
  target_worktree_root_dir`, `worktrees_by_branch.get(branch)`, ...) -
  mixing native and posix separators on Windows would silently miscompare
  paths produced by Python helpers vs. paths returned by `git` itself,
* user-facing output and test snapshots (one form across all platforms,
  matching `git`'s own output style),
* cross-platform consistency of any path stored long-term in
  git-machete's state (caches, branch-layout-file path, ...).

Pure I/O (`open`, `os.path.isfile`, `shutil.*`, `subprocess.run(cwd=...)`)
accepts either form on Windows, so the normalisation is invisible there -
the value lies in the type-system guarantee that downstream comparisons
and renders are stable.

The `Path` / `AbsPath` hierarchy mirrors the discipline used for branch
names (`AnyBranchName` / `LocalBranchShortName` etc.): production code
converts raw `str`s at the earliest boundary, so the type system enforces
"absolute" semantics where a stored path must outlive a possible
`os.chdir` (most notably `traverse` switching into linked worktrees -
the latent source of issue #1681 and friends).
"""

import os
from pathlib import Path as PyPath
from pathlib import PurePath, PurePosixPath

from git_machete.utils.exceptions import UnexpectedMacheteException


class Path(str):
    """A filesystem path (relative or absolute), always in posix form."""

    def __new__(cls, value: str = "") -> "Path":
        # Normalise once at the boundary so every typed path is guaranteed
        # forward-slash. `PurePath` is platform-aware: on Windows it converts
        # `\` to `/`, on POSIX it's a no-op for sane inputs. We still go
        # through `as_posix()` so the invariant holds even if the input was
        # already posix-form on Windows.
        return super().__new__(cls, PurePath(value).as_posix() if value else "")

    @staticmethod
    def of(value: str) -> "Path":
        if not value:
            raise UnexpectedMacheteException(
                f"Path.of should not accept {value!r} as a param.")
        return Path(value)


class AbsPath(Path):
    """A path confirmed absolute at construction time, in posix form."""

    @staticmethod
    def of(value: str) -> "AbsPath":
        if not value:
            raise UnexpectedMacheteException(
                f"AbsPath.of should not accept {value!r} as a param.")
        if not os.path.isabs(value):
            raise UnexpectedMacheteException(
                f"AbsPath.of expects an absolute path, got {value!r}.")
        return AbsPath(value)

    @staticmethod
    def home() -> "AbsPath":
        """The current user's home directory, posix-form."""
        return AbsPath.of(str(PyPath.home()))

    def join_fragments(self, *fragments: str) -> "AbsPath":
        """Append `fragments` (path segments, not absolute paths themselves)
        under this absolute base; result is also absolute.

        Named `join_fragments` rather than `join` (which `str` already
        defines with unrelated semantics) or `join_paths` (the args are
        plain segments like `"machete"`, not standalone paths).
        """
        return AbsPath(str(PurePosixPath(self, *fragments)))


def join_paths(*paths: str) -> Path:
    return Path(str(PurePosixPath(*paths)))


def abs_path(path: str) -> AbsPath:
    return AbsPath(PyPath(path).resolve().as_posix())


def rel_path(path: str) -> Path:
    return Path(os.path.relpath(path))
