.. _reapply:

reapply
=======
**Usage:**

.. code-block:: shell

    git machete reapply [-f|--fork-point=<fork-point-commit>]

Interactively rebase the current branch on the top of its computed fork point.
The chunk of the history to be rebased starts at the automatically computed fork point of the current branch by default,
but can also be set explicitly by ``--fork-point``.
See help for :ref:`fork-point` for more details on meaning of the *fork point*.

Note: the current reapplied branch does not need to occur in the branch layout file.

Tip: ``reapply`` can be used for squashing the commits on the current branch to make history more condensed before push to the remote,
but there is also dedicated ``squash`` command that achieves the same goal without running ``git rebase``.

**Options:**

-f, --fork-point=<fork-point-commit>    Specifies the alternative fork point commit after which the rebased part of history is meant to start.

**Environment variables:**

``GIT_MACHETE_REBASE_OPTS``
    Extra options to pass to the underlying ``git rebase`` invocation, space-separated.
    Example: ``GIT_MACHETE_REBASE_OPTS="--keep-empty --rebase-merges" git machete reapply``.
