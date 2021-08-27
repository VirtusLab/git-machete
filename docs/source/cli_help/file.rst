.. _file:

file
----
**Usage:**

.. code-block:: shell

    git machete file

Outputs the absolute path of the machete definition file. Currently fixed to ``<git-directory>/machete``.
Note: this won't always be just ``<repo-root>/.git/machete`` since e.g. submodules and worktrees have their git directories in different location.
