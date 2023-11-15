.. _prune:

prune
=====
**Usage:**

.. code-block:: shell

    git machete prune [-y|--yes]

Delete managed branches whose remote tracking branches have been deleted and have no downstreams.
In other words, this deletes all branches except

    1. those that are unmanaged,
    2. those that have no remote tracking branch set (unpushed),
    3. those whose remote tracking branches still exist (not deleted remotely),
    4. those that have a downstream branch (are still part of a stack).

No branch will be deleted unless explicitly confirmed by the user (or unless ``-y/--yes`` option is passed).

**Options:**

-y, --yes                  Don't ask for confirmation when deleting branches from git.
