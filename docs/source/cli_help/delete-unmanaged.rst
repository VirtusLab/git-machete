.. _delete-unmanaged:

delete-unmanaged
----------------
**Usage:**

.. code-block:: shell

    git machete delete-unmanaged [-y|--yes]

Goes one-by-one through all the local git branches that don't exist in the definition file,
and ask to delete each of them (with ``git branch -d`` or ``git branch -D``) if confirmed by user.
No branch will be deleted unless explicitly confirmed by the user (or unless ``-y/--yes`` option is passed).

Note: this should be used with care since deleting local branches can sometimes make it impossible for ``git machete`` to properly figure out fork points.
See :ref:`fork-point` for more details.

**Options:**

-y, --yes          Don't ask for confirmation.
