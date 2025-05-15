.. raw:: html

    <style> .green {color:green} </style>
    <style> .yellow {color:#FFBF00} </style>

.. role:: green
.. role:: yellow


.. _fork-point:

fork-point
==========
**Usage:**

.. code-block:: shell

  git machete fork-point [--inferred] [<branch>]
  git machete fork-point --override-to=<revision>|--override-to-inferred|--override-to-parent [<branch>]
  git machete fork-point --unset-override [<branch>]

Note: in all three forms, if no ``<branch>`` is specified, the currently checked out branch is assumed.
The branch in question does not need to occur in the branch layout file.


Without any option, ``git machete fork-point`` displays full hash of the fork point commit for ``<branch>``.
Fork point of the given ``<branch>`` is the commit at which the history of ``<branch>`` diverges from history of any other branch.

Fork point is assumed by many ``git machete`` commands as the place where the unique history of ``<branch>`` starts.
The range of commits between the fork point and the tip of the given branch is, for instance:

* listed for each branch by ``git machete status --list-commits``
* passed to ``git rebase`` by ``git machete`` ``reapply``/``slide-out``/``traverse``/``update``
* provided to ``git diff``/``log`` by ``git machete`` ``diff``/``log``.

``git machete`` assumes fork point of ``<branch>`` is the most recent commit in the log of ``<branch>`` that has NOT been introduced on that very branch,
but instead occurs on a reflog (see help for ``git reflog``) of some other branch.
This yields a correct result in typical cases, but there are some situations
(esp. when some local branches have been deleted) where the fork point might not be determined correctly.
Thus, all rebase-involving operations (``reapply``, ``slide-out``, ``traverse`` and ``update``) run ``git rebase`` in the interactive mode by default,
unless told explicitly not to do so by ``--no-interactive-rebase`` flag. This way, the suggested commit range can be inspected before the rebase starts.
Also, ``reapply``, ``slide-out``, ``squash``, and ``update`` allow to specify the fork point explicitly by a command-line option.

``git machete fork-point`` is different (and more powerful) than ``git merge-base --fork-point``,
since the latter takes into account only the reflog of the one provided upstream branch,
while the former scans reflogs of all local branches and their remote tracking branches.
This makes git machete's ``fork-point`` more resilient to modifications of ``.git/machete`` :ref:`file` when certain branches are re-attached under new parents (upstreams).

With ``--override-to-parent``, overrides fork point of ``<branch>`` to the commit pointed by ``<branch>``'s parent in branch layout.
The override data is stored under ``machete.overrideForkPoint.<branch>.to`` git config key.
Note: the override only works as long as parent of ``<branch>`` is an ancestor of current ``<branch>`` commit.

With ``--override-to=<revision>``, overrides fork point of ``<branch>`` to the selected commit.
Note: this option is **deprecated** since it may lead to confusing user experience (due to the "hidden" commits between fork point and parent branch in green-edge case).
Use ``--override-to-parent``, or rebase the branch onto its parent with ``git machete update --fork-point=<revision>``.

With ``--inferred``, displays the commit that ``git machete fork-point`` infers to be fork point of ``<branch>``.
If there is NO fork point override for ``<branch>``, this is identical to the output of ``git machete fork-point``.
If there is a fork point override for ``<branch>``, this is identical to the what the output of ``git machete fork-point`` would be if the override was NOT present.
Note: this piece of information is also displayed by ``git machete status --list-commits`` in case a :yellow:`yellow` edge occurs.

With ``--override-to-inferred`` option, overrides fork point of ``<branch>`` to the result of ``git machete fork-point --inferred`` for ``<branch>``.
Note: similarly to ``--override-to=<revision>``, this option is **deprecated**.

With ``--unset-override``, the fork point override for ``<branch>`` is unset.
This is simply done by removing the corresponding ``machete.overrideForkPoint.<branch>.to`` git config entry.


Note: if branch ``B`` has an overridden fork point, then ``B`` is considered to be connected with a :green:`green` edge to its upstream (parent) ``U``,
even if the overridden fork point of ``B`` is NOT equal to the commit pointed by ``U``.
