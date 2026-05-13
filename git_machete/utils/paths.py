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


class Path(str):
    """A filesystem path (relative or absolute), always in posix form.

    All normalisation and invariants happen in `__new__` so that
    `Path(value)` / `AbsPath(value)` is the single, obvious way to obtain
    a typed path - there are intentionally no `.of(...)` factory methods.
    """

    def __new__(cls, value: str = "") -> "Path":
        # `PurePath` is platform-aware: on Windows it parses both `\` and `/`
        # as separators, on POSIX only `/`. `str(PurePath(...))` then renders
        # back to the platform-native form (so `str(PurePath("a/b"))` is
        # `"a\\b"` on Windows). `as_posix()` instead always renders with `/`,
        # which is the invariant we want every typed path to satisfy.
        return super().__new__(cls, PurePath(value).as_posix())

    @staticmethod
    def join_paths(*paths: str) -> "Path":
        """Combine one or more path-like strings into a single `Path`.

        Inputs may be relative or absolute; downstream semantics follow
        `PurePosixPath`'s join rules (an absolute fragment discards
        anything before it).

        We use `PurePosixPath` (rather than the platform-aware `PurePath`)
        for joining because `Path.__new__` has already normalised any
        prior typed segment to forward-slash form, so the inputs here
        are guaranteed posix-style on every platform - `PurePosixPath`
        states that intent explicitly and avoids the Windows-only
        drive-letter / backslash parsing that `PureWindowsPath` would do.
        The result still passes through `Path.__new__` for a final
        normalisation pass (cheap, idempotent).
        """
        return Path(str(PurePosixPath(*paths)))

    @staticmethod
    def relative(value: str) -> "Path":
        """Express `value` relative to the current working directory."""
        return Path(os.path.relpath(value))


class AbsPath(Path):
    """A path confirmed absolute at construction time, in posix form.

    `AbsPath(value)` resolves `value` against the current working
    directory if it isn't already absolute, follows symlinks and
    collapses `.`/`..` segments via `pathlib.Path.resolve`. The
    resulting instance is canonical and stable across `os.chdir`.
    """

    def __new__(cls, value: str = "") -> "AbsPath":
        return str.__new__(cls, PyPath(value).resolve().as_posix())

    @staticmethod
    def home() -> "AbsPath":
        """The current user's home directory, posix-form."""
        return AbsPath(str(PyPath.home()))

    def parent_dir(self) -> "AbsPath":
        """The directory containing this path.

        For the filesystem root, returns the root itself (so the caller
        can use this in a loop without an extra guard against runaway
        traversal).
        """
        return AbsPath(str(PyPath(self).parent))

    def join_fragments(self, *fragments: str) -> "AbsPath":
        """Append `fragments` (path segments, not absolute paths themselves)
        under this absolute base; result is also absolute.

        `PurePosixPath` is used here for the same reason as in
        `Path.join_paths`: `self` is already a posix-form `AbsPath`, so
        we want a join engine that doesn't try to reinterpret the input
        on Windows. The final renormalisation happens in `AbsPath.__new__`
        via `pathlib.Path.resolve().as_posix()`.
        """
        return AbsPath(str(PurePosixPath(self, *fragments)))
