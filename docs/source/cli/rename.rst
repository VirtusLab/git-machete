.. _rename:

rename
======
**Usage:**

.. code-block:: shell

    git machete rename [-b|--branch=<branch>] [--repoint-tracking] <new-name>

Renames the given branch (or the current branch, if ``-b``/``--branch`` is not specified) to ``<new-name>``
in both the local git repository and in the branch layout file.

Under the hood, ``git branch -m`` is used to rename the branch, which also automatically migrates
the branch's remote tracking configuration to the new name.
As a result, after the rename the local branch still tracks the same remote branch as before
(for example ``origin/old-name``), unless ``--repoint-tracking`` is given.

Note: ``rename`` does **not** rename the branch on the remote — it only renames the local branch.
The remote branch is left intact and can still be pushed to under its original name.

**Options:**

-b, --branch=<branch>   Branch to rename; if not given, the current branch is renamed.

--repoint-tracking     After the rename, try to set the tracking branch to ``<remote>/<new-name>``.
                        If ``<remote>/<new-name>`` does not exist, the tracking is unset instead.
                        Without this flag the tracking branch is left pointing to the same remote
                        branch it pointed to before (for example ``origin/old-name``).
