.. _log:

log
---
**Usage:**

.. code-block:: shell

    git machete l[og] [<branch>]

Runs ``git log`` for the range of commits from tip of the given branch (or current branch, if none specified) back to its fork point.
See :ref:`fork-point` for more details on meaning of the *fork point*.

Note: the branch in question does not need to occur in the definition file.
