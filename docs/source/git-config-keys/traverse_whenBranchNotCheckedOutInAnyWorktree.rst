Controls the behavior of ``git machete traverse`` when checking out a branch that is not currently checked out in any worktree.

The default value is ``cd-into-main-worktree``, which means that ``traverse`` will change directory to the main worktree before checking out the branch.

Set to ``stay-in-the-current-worktree`` to make ``traverse`` stay in whatever worktree has already been reached by that point,
and check out the branch there instead.
Note that this worktree might be different then the initial working directory where ``traverse`` started.
