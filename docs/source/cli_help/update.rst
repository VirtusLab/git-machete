.. _update:

update
------
**Usage:**

.. code-block:: shell

    git machete update [-f|--fork-point=] [-M|--merge] [-n|--no-edit-merge|--no-interactive-rebase]

Synchronizes the current branch with its upstream (parent) branch either by rebase (default) or by merge (if ``--merge`` option passed).

If updating by rebase, interactively rebases the current branch on the top of its upstream (parent) branch.
The chunk of the history to be rebased starts at the fork point of the current branch, which by default is inferred automatically, but can also be set explicitly by ``--fork-point``.
See :ref:`fork-point` for more details on meaning of the *fork point*.

If updating by merge, merges the upstream (parent) branch into the current branch.

**Options:**

-f, --fork-point=<fork-point-commit>    If updating by rebase, specifies the alternative fork point commit after which the rebased part of history is meant to start. Not allowed if updating by merge.

-M, --merge                             Update by merge rather than by rebase.

-n                                      If updating by rebase, equivalent to ``--no-interactive-rebase``. If updating by merge, equivalent to ``--no-edit-merge``.

--no-edit-merge                         If updating by merge, skip opening the editor for merge commit message while doing ``git merge`` (i.e. pass ``--no-edit`` flag to underlying ``git merge``). Not allowed if updating by rebase.

--no-interactive-rebase                 If updating by rebase, run ``git rebase`` in non-interactive mode (without ``-i/--interactive`` flag). Not allowed if updating by merge.

**Environment variables:**

``GIT_MACHETE_REBASE_OPTS``
    Extra options to pass to the underlying ``git rebase`` invocation, space-separated.

    Example: ``GIT_MACHETE_REBASE_OPTS="--keep-empty --rebase-merges" git machete update``.
