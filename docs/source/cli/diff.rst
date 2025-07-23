.. _diff:

diff
====
**Usage:**

.. code-block:: shell

    git machete d[iff] [-s|--stat] [<branch>] [-- <pass-through-arguments>]

Runs ``git diff`` of the given branch tip against its fork point or, if none specified,
of the current working tree against the fork point of the currently checked out branch.
See help for :ref:`fork-point` for more details.

Note: the branch in question does not need to occur in the branch layout file.

**Options:**

-- <pass-through-arguments>    Arguments to pass directly to the underlying ``git diff``, for example ``git machete diff -- --name-only``.

-s, --stat                     Make ``git machete diff`` pass ``--stat`` option to ``git diff``, so that only summary (diffstat) is printed.
