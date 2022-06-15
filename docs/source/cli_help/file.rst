.. _file:

file
----
**Usage:**

.. code-block:: shell

    git machete file

Outputs the absolute path of machete definition file.
The file is always called ``machete`` and is located in the git directory of the project.

Three cases are possible:
    * if ``git machete`` is executed from a regular working directory (not a worktree or submodule), the file is located under ``.git/machete``,
    * if ``git machete`` is executed from a **worktree**, the file path depends on the ``machete.worktree.useTopLevelMacheteFile`` config key value:

        * if ``machete.worktree.useTopLevelMacheteFile`` is true, the file is located under ``.git/machete``
        * if ``machete.worktree.useTopLevelMacheteFile`` is false (default), the file is located under ``.git/worktrees/.../machete``,
    * if ``git machete`` is executed from a **submodule**, this file is located in the git folder of the submodule itself under ``.git/modules/.../machete``.
