.. _file:

file
----
**Usage:**

.. code-block:: shell

    git machete file

Outputs the absolute path of machete definition file.
The file is always called ``machete`` and is located in the git directory of the project.

Three cases are possible:
    * if ``git machete`` is executed from a regular working directory (not a worktree or submodule), this simply resolves to ``machete`` in .git folder,
    * if ``git machete`` is executed from a **worktree**, this resolves to ``machete`` in the .git folder of the **top-level project** (not the worktree's .git folder!),
    * if ``git machete`` is executed from a **submodule**, this resolves to ``machete`` in the .git folder of the **submodule** itself (not the top-level project's .git folder!).
