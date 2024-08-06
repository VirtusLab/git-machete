.. raw:: html

    <style> .green {color:green} </style>
    <style> .grey {color:dimgrey} </style>
    <style> .red {color:red} </style>
    <style> .yellow {color:#FFBF00} </style>

.. role:: green
.. role:: grey
.. role:: red
.. role:: yellow

.. _traverse:

traverse
========
**Usage:**

.. code-block:: shell

    git machete t[raverse] [-F|--fetch] [-l|--list-commits] [-M|--merge]
                           [-n|--no-edit-merge|--no-interactive-rebase] [--[no-]push] [--[no-]push-untracked]
                           [--return-to=WHERE] [--start-from=WHERE] [--squash-merge-detection=MODE]
                           [-w|--whole] [-W] [-y|--yes]

Traverses the branches in the order as they occur in branch layout file.
By default, ``traverse`` starts from the current branch.
This behavior can, however, be customized using options: ``--start-from=``, ``--whole`` or ``-w``, ``-W``.

For each branch, the command:

* detects if the branch is merged (:grey:`grey` edge) to its parent (aka upstream):

  - by commit equivalency (default), or by strict detection of merge commits (if ``--no-detect-squash-merges`` passed),
  - if so, asks the user whether to **slide out** the branch from the dependency tree (typically branches are no longer needed after they're merged);

* otherwise, if the branch has a :red:`red` or :yellow:`yellow` edge to its parent/upstream (see help for :ref:`status`):

  - asks the user whether to **rebase** (default) or merge (if ``--merge`` passed) the branch onto into its upstream branch
    --- equivalent to ``git machete update``;

* if the branch is not tracked on a remote, is ahead of its remote counterpart, or diverged from the counterpart &
  has newer head commit than the counterpart:

  - asks the user whether to **push** the branch (possibly with ``--force-with-lease`` if the branches diverged);

* otherwise, if the branch diverged from the remote counterpart & has older head commit than the counterpart:

  - asks the user whether to **reset** (``git reset --keep``) the branch to its remote counterpart

* otherwise, if the branch is behind its remote counterpart:

  - asks the user whether to **pull** the branch;

* and finally, if any of the above operations has been successfully completed:

  - prints the updated ``status``.

By default ``traverse`` asks if the branch should be pushed. This behavior can, however, be changed with the ``machete.traverse.push`` configuration key.
It can also be customized using options: ``--[no-]push`` or ``--[no-]push-untracked`` --- the order of the flags defines their precedence over each other
(the one on the right overriding the ones on the left). More on them in the **Options** section below.

If the traverse flow is stopped (typically due to merge/rebase conflicts), just run ``git machete traverse`` after the merge/rebase is finished.
It will pick up the walk from the current branch.
Unlike with ``git rebase`` or ``git cherry-pick``, there is no special ``--continue`` flag, as ``traverse`` is stateless.
``traverse`` does **not** keep a state of its own like ``git rebase`` does in ``.git/rebase-apply/``.

The rebase, push and slide-out behaviors of ``traverse`` can also be customized for each branch separately using *branch qualifiers*.
There are ``push=no``, ``rebase=no`` and ``slide-out=no`` qualifiers that can be used to opt out of default behavior (rebasing, pushing and sliding the branch out).
The qualifier can appear anywhere in the annotation, but needs to be separated by a whitespace from any other character, as in: ``some_annotation_text rebase=no push=no slide-out=no``.
Qualifiers can only be overwritten by manually editing ``.git/machete`` file or modifying it with ``git machete e[dit]``, or by updating annotations with ``git machete anno``.
Example machete file with branch qualifiers:

.. code-block::

    master
      develop  rebase=no slide-out=no
        my-branch  PR #123
        someone-elses-branch  PR #124 rebase=no push=no
        branch-for-local-experiments  push=no

Operations like ``git machete github anno-prs`` (``git machete gitlab anno-mrs``)
and ``git machete github checkout-prs`` (``git machete gitlab checkout-mrs``) add ``rebase=no push=no`` branch qualifiers
when the current user is NOT the author of the PR/MR associated with that branch.


**Options:**

-F, --fetch                    Fetch the remotes of all managed branches at the beginning of traversal (no ``git pull`` involved, only ``git fetch``).

-l, --list-commits             When printing the status, additionally list the messages of commits introduced on each branch.

-M, --merge                    Update by merge rather than by rebase.

-n                             If updating by rebase, equivalent to ``--no-interactive-rebase``. If updating by merge, equivalent to ``--no-edit-merge``.

--no-detect-squash-merges      **Deprecated**, use ``--squash-merge-detection=none`` instead.
                               Only consider *strict* (fast-forward or 2-parent) merges, rather than rebase/squash merges,
                               when detecting if a branch is merged into its upstream (parent).

--no-edit-merge                If updating by merge, skip opening the editor for merge commit message while doing ``git merge``
                               (that is, pass ``--no-edit`` flag to the underlying ``git merge``). Not allowed if updating by rebase.

--no-interactive-rebase        If updating by rebase, run ``git rebase`` in non-interactive mode (without ``-i/--interactive`` flag).
                               Not allowed if updating by merge.

--no-push                      Do not push any (neither tracked nor untracked) branches to remote, re-enable via ``--push``.

--no-push-untracked            Do not push untracked branches to remote, re-enable via ``--push-untracked``.

--push                         Push all (both tracked and untracked) branches to remote --- default behavior. Default behavior can be changed
                               by setting git configuration key ``git config machete.traverse.push false``.
                               Configuration key value can be overridden by the presence of the flag.

--push-untracked               Push untracked branches to remote.

--return-to=WHERE              Specifies the branch to return after traversal is successfully completed;
                               WHERE can be ``here`` (the current branch at the moment when traversal starts), ``nearest-remaining``
                               (nearest remaining branch in case the ``here`` branch has been slid out by the traversal) or
                               ``stay`` (the default --- just stay wherever the traversal stops). Note: when user quits by ``q``/``yq``
                               or when traversal is stopped because one of git actions fails, the behavior is always ``stay``.

--squash-merge-detection=MODE  Specifies the mode for detection of rebase/squash merges (grey edges).
                               ``MODE`` can be ``none`` (fastest, no squash merges are detected), ``simple`` (default) or ``exact`` (slowest).
                               See the below paragraph on ``machete.squashMergeDetection`` git config key for more details.

--start-from=WHERE             Specifies the branch to start the traversal from; WHERE can be ``here``
                               (the default --- current branch, must be managed by git machete), ``root`` (root branch of the current branch,
                               as in ``git machete show root``) or ``first-root`` (first listed managed branch).

-w, --whole                    Equivalent to ``-n --start-from=first-root --return-to=nearest-remaining``;
                               useful for quickly traversing & syncing all branches (rather than doing more fine-grained operations on the
                               local section of the branch tree).

-W                             Equivalent to ``--fetch --whole``; useful for even more automated traversal of all branches.

-y, --yes                      Don't ask for any interactive input, including confirmation of rebase/push/pull. Implies ``-n``.

**Environment variables:**

``GIT_MACHETE_REBASE_OPTS``
    Extra options to pass to the underlying ``git rebase`` invocations, space-separated.
    Example: ``GIT_MACHETE_REBASE_OPTS="--keep-empty --rebase-merges" git machete traverse``.

**Git config keys:**

``machete.squashMergeDetection``:
    .. include:: git-config-keys/squashMergeDetection.rst

``machete.traverse.push``
    .. include:: git-config-keys/traverse_push.rst
