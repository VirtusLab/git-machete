.. _slide-out:

slide-out
=========
**Usage:**

.. code-block:: shell

    git machete slide-out --all-merged [--delete]
    git machete slide-out [-d|--down-fork-point=<down-fork-point-commit>] [--delete] [-M|--merge] [-n|--no-edit-merge|--no-interactive-rebase] [<branch> [<branch> [<branch> ...]]]

Removes the given branch (or multiple branches) from the branch layout.
If no branch has been specified, current branch is slid out.
If ``--all-merged`` is specified, all branches that have been removed from the remote are slid out.

Also, if the last branch in the specified chain of ``[<branch> [<branch>]]`` had any children,
these child branches are synced to the parent of the first specified branch.
Sync is performed either by rebase (default) or by merge (if ``--merge`` option passed).

For example, let's assume the following dependency tree:

.. code-block::

    develop
        adjust-reads-prec
            block-cancel-order
                change-table
                    drop-location-type
                add-notification

After running ``git machete slide-out adjust-reads-prec block-cancel-order`` the tree will be reduced to:

.. code-block::

    develop
        change-table
            drop-location-type
        add-notification

and ``change-table`` and ``add-notification`` will be rebased onto develop (fork point for this rebase is configurable, see ``-d`` option below).

The most common use is to slide out a single branch whose upstream was a ``develop``/``master`` branch and that has been recently merged.

The provided branches must form a chain --- all of the following conditions must be met:

    * for i=1..N-1, (i+1)-th branch must be the only downstream (child) branch of the i-th branch,
    * all provided branches must have an upstream branch (so, in other words, roots of branch dependency tree cannot be slid out).

Note: Unless ``--delete`` is passed, this command doesn't delete any branches from git, just removes them from the tree of branch dependencies.

**Options:**

--all-merged                                      Slide out managed branches whose remote tracking branches have been deleted and that have no downstreams.
                                                  In other words, this deletes all branches except:
                                                  1. those that are unmanaged,
                                                  2. those that have no remote tracking branch set (unpushed),
                                                  3. those whose remote tracking branches still exist (not deleted remotely),
                                                  4. those that have at least one downstream (child) branch.

-d, --down-fork-point=<down-fork-point-commit>    If updating by rebase, specifies the alternative fork point for downstream branches for the operation.
                                                  ``git machete fork-point`` overrides for downstream branches are recommended over use of this option.
                                                  See also doc for ``--fork-point`` option in ``git machete help reapply`` and ``git machete help update``.
                                                  Not allowed if updating by merge.

--delete                                          Delete the branches after sliding them out.

-M, --merge                                       Update the downstream branch by merge rather than by rebase.

-n                                                If updating by rebase, equivalent to ``--no-interactive-rebase``.
                                                  If updating by merge, equivalent to ``--no-edit-merge``.

--no-edit-merge                                   If updating by merge, skip opening the editor for merge commit message while doing
                                                  ``git merge`` (that is, pass ``--no-edit`` flag to the underlying ``git merge``).
                                                  Not allowed if updating by rebase.

--no-interactive-rebase                           If updating by rebase, run ``git rebase`` in non-interactive mode (without ``-i/--interactive`` flag).
                                                  Not allowed if updating by merge.

**Environment variables:**

``GIT_MACHETE_REBASE_OPTS``
    Extra options to pass to the underlying ``git rebase`` invocations, space-separated.
    Example: ``GIT_MACHETE_REBASE_OPTS="--keep-empty --rebase-merges" git machete slide-out``.
