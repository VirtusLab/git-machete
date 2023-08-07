.. _is-managed:

is-managed
==========
**Usage:**

.. code-block:: shell

    git machete is-managed [<branch>]

Returns with zero exit code if the given branch (or current branch, if none specified) is managed by git machete (i.e. listed in .git/machete).

Returns with a non-zero exit code in case:

    * the <branch> is provided but isn't managed (or doesn't exist), or
    * the <branch> isn't provided and the current branch isn't managed, or
    * the <branch> isn't provided and there's no current branch (detached HEAD).
