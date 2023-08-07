.. _diff:

diff
====
**Usage:**

.. code-block:: shell

    git machete d[iff] [-s|--stat] [<branch>]

Runs ``git diff`` of the given branch tip against its fork point or, if none specified,
of the current working tree against the fork point of the currently checked out branch.
See help for :ref:`fork-point` for more details on the meaning of *fork point*.

Note: the branch in question does not need to occur in the definition file.

**Options:**

-s, --stat    Makes ``git machete diff`` pass ``--stat`` option to ``git diff``, so that only summary (diffstat) is printed.
