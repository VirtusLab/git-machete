.. _edit:

edit
----
**Usage:**

.. code-block:: shell

    git machete e[dit]

Opens an editor and lets you edit the definition file manually.

The editor is determined by checking up the following locations:

    * ``$GIT_MACHETE_EDITOR``
    * ``$GIT_EDITOR``
    * ``$(git config core.editor)``
    * ``$VISUAL``
    * ``$EDITOR``
    * ``editor``
    * ``nano``
    * ``vi``

and selecting the first one that is defined and points to an executable file accessible on ``PATH``.

Note that the above editor selection only applies for editing the definition file,
but not for any other actions that may be indirectly triggered by git machete, including editing of rebase TODO list, commit messages etc.

The definition file can be always accessed and edited directly under the path returned by ``git machete file``
(usually ``.git/machete``, unless worktrees or submodules are involved).

**Environment variables:**

``GIT_MACHETE_EDITOR``
    Name of the editor executable.
