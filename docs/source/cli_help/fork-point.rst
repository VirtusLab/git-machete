.. raw:: html

    <style> .green {color:green} </style>
    <style> .yellow {color:#FFBF00} </style>

.. role:: green
.. role:: yellow


.. _fork-point:

fork-point
----------
**Usage:**

.. code-block:: shell

  git machete fork-point [--inferred] [<branch>]
  git machete fork-point --override-to=<revision>|--override-to-inferred|--override-to-parent [<branch>]
  git machete fork-point --unset-override [<branch>]

Note: in all three forms, if no ``<branch>`` is specified, the currently checked out branch is assumed.
The branch in question does not need to occur in the definition file.


Without any option, displays full hash of the fork point commit for the ``<branch>``.
Fork point of the given ``<branch>`` is the commit at which the history of the ``<branch>`` diverges from history of any other branch.

Fork point is assumed by many ``git machete`` commands as the place where the unique history of the ``<branch>`` starts.
The range of commits between the fork point and the tip of the given branch is, for instance:

    * listed for each branch by ``git machete status --list-commits``
    * passed to ``git rebase`` by ``git machete`` ``reapply``/``slide-out``/``traverse``/``update``
    * provided to ``git diff``/``log`` by ``git machete`` ``diff``/``log``.

``git machete`` assumes fork point of ``<branch>`` is the most recent commit in the log of ``<branch>`` that has NOT been introduced on that very branch,
but instead occurs on a reflog (see help for ``git reflog``) of some other, usually chronologically earlier, branch.
This yields a correct result in typical cases, but there are some situations
(esp. when some local branches have been deleted) where the fork point might not be determined correctly.
Thus, all rebase-involving operations (``reapply``, ``slide-out``, ``traverse`` and ``update``) run ``git rebase`` in the interactive mode by default,
unless told explicitly not to do so by ``--no-interactive-rebase`` flag, so that the suggested commit range can be inspected before the rebase commences.
Also, ``reapply``, ``slide-out``, ``squash``, and ``update`` allow to specify the fork point explicitly by a command-line option.

``git machete fork-point`` is different (and more powerful) than ``git merge-base --fork-point``,
since the latter takes into account only the reflog of the one provided upstream branch,
while the former scans reflogs of all local branches and their remote tracking branches.
This makes git machete's ``fork-point`` more resilient to modifications of ``.git/machete`` :ref:`file` where certain branches are re-attached under new parents (upstreams).


With ``--override-to=<revision>``, sets up a fork point override for ``<branch>``.
Fork point for ``<branch>`` will be overridden to the provided <revision> (commit) as long as the ``<branch>`` still points to (or is descendant of) that commit.
Even if revision is a symbolic name (e.g. other branch name or ``HEAD~3)`` and not explicit commit hash (like ``a1b2c3ff``),
it's still resolved to a specific commit hash at the moment the override is set up (and not later when the override is actually used).
The override data is stored under ``machete.overrideForkPoint.<branch>.to`` git config key.
Note: the provided fork point <revision> must be an ancestor of the current ``<branch>`` commit.

With ``--override-to-parent``, overrides fork point of the ``<branch>`` to the commit currently pointed by ``<branch>``'s parent in the branch dependency tree.
Note: this will only work if ``<branch>`` has a parent at all (i.e. is not a root) and parent of ``<branch>`` is an ancestor of current ``<branch>`` commit.

With ``--inferred``, displays the commit that ``git machete fork-point`` infers to be the fork point of ``<branch>``.
If there is NO fork point override for ``<branch>``, this is identical to the output of ``git machete fork-point``.
If there is a fork point override for ``<branch>``, this is identical to the what the output of ``git machete fork-point`` would be if the override was NOT present.

With ``--override-to-inferred`` option, overrides fork point of the ``<branch>`` to the commit that ``git machete fork-point`` infers to be the fork point of ``<branch>``.
Note: this piece of information is also displayed by ``git machete status --list-commits`` in case a :yellow:`yellow` edge occurs.

With ``--unset-override``, the fork point override for ``<branch>`` is unset.
This is simply done by removing the corresponding ``machete.overrideForkPoint.<branch>.to`` config entry.


Note: if an overridden fork point applies to a branch ``B``, then it's considered to be connected with a :green:`green` edge to its upstream (parent) ``U``,
even if the overridden fork point of ``B`` is NOT equal to the commit pointed by ``U``.
