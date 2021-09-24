.. _slide-out:

slide-out
---------
**Usage:**

.. code-block:: shell

    git machete slide-out [-d|--down-fork-point=<down-fork-point-commit>] [-M|--merge] [-n|--no-edit-merge|--no-interactive-rebase] [<branch> [<branch> [<branch> ...]]]

Removes the given branch (or multiple branches) from the branch tree definition.  If no branch has been specified current branch is assumed as the only branch.
Then synchronizes the downstream (child) branches of the last specified branch on the top of the upstream (parent) branch of the first specified branch.
Sync is performed either by rebase (default) or by merge (if ``--merge`` option passed).

The most common use is to slide out a single branch whose upstream was a ``develop``/``master`` branch and that has been recently merged.

Since this tool is designed to perform only one single rebase/merge at the end, provided branches must form a chain, i.e. all of the following conditions must be met:

    * for i=1..N-1, (i+1)-th branch must be the only downstream (child) branch of the i-th branch,
    * all provided branches must have an upstream branch (so, in other words, roots of branch dependency tree cannot be slid out).

For example, let's assume the following dependency tree:

.. code-block::

    develop
        adjust-reads-prec
            block-cancel-order
                change-table
                    drop-location-type
                add-notification

And now let's assume that ``adjust-reads-prec`` and later ``block-cancel-order`` were merged to develop.
After running ``git machete slide-out adjust-reads-prec block-cancel-order`` the tree will be reduced to:

.. code-block::

    develop
        change-table
            drop-location-type
        add-notification

and ``change-table`` and ``add-notification`` will be rebased onto develop (fork point for this rebase is configurable, see ``-d`` option below).

Note: This command doesn't delete any branches from git, just removes them from the tree of branch dependencies.

**Options:**

  -d, --down-fork-point=<down-fork-point-commit>    If updating by rebase, specifies the alternative fork point for downstream branches for the operation.
                                                    ``git machete fork-point`` overrides for downstream branches are recommended over use of this option.
                                                    See also doc for ``--fork-point`` option in ``git machete help reapply`` and ``git machete help update``.
                                                    Not allowed if updating by merge.

  -M, --merge                                       Update the downstream branch by merge rather than by rebase.

  -n                                                If updating by rebase, equivalent to ``--no-interactive-rebase``. If updating by merge, equivalent to ``--no-edit-merge``.

  --no-edit-merge                                   If updating by merge, skip opening the editor for merge commit message while doing ``git merge`` (i.e. pass ``--no-edit`` flag to underlying ``git merge``).
                                                    Not allowed if updating by rebase.

  --no-interactive-rebase                           If updating by rebase, run ``git rebase`` in non-interactive mode (without ``-i/--interactive`` flag).
                                                    Not allowed if updating by merge.
