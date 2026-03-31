Controls the behavior of ``git machete traverse`` when it needs to act on a branch that is not currently checked out in any worktree.

Allowed values:

* ``cd-into-main-worktree`` (default): change directory to the main worktree and check out the branch there.

* ``stay-in-the-current-worktree``: check out the branch in whichever worktree ``traverse`` is currently operating in,
  without changing directory. Note that this worktree might differ from the one where ``traverse`` originally started.

* ``cd-into-temporary-worktree``: create a new worktree in a temporary directory, check out the branch there,
  and remove this temporary worktree once ``traverse`` moves on to the next branch (or finishes).
  This ensures that no existing (non-temporary) worktree has its checked-out branch changed by ``traverse``.
