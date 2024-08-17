.. _log:

log
===
**Usage:**

.. code-block:: shell

    git machete l[og] [<branch>] [-- <pass-through-arguments>]

Runs ``git log`` for the range of commits from tip of the given branch (or current branch, if none specified) back to its fork point.
See help for :ref:`fork-point` for more details on meaning of the *fork point*.

Note: the branch in question does not need to occur in the branch layout file.

**Options:**

-- <pass-through-arguments>    Arguments to pass directly to the underlying ``git log``, for example ``git machete log -- --patch``.
