.. _list:

list
====
**Usage:**

.. code-block:: shell

    git machete list <category>

where <category> is one of: ``addable``, ``childless``, ``managed``, ``slidable``, ``slidable-after <branch>``, ``unmanaged``, ``with-overridden-fork-point``.

Lists all branches that fall into one of the specified categories:

* ``addable``: all branches (local or remote) than can be added to the branch layout file,
* ``childless``: all managed branches that do not possess child branches,
* ``managed``: all branches that appear in the branch layout file,
* ``slidable``: all managed branches that have an upstream and can be slid out with :ref:`slide-out` command
* ``slidable-after <branch>``: the downstream branch of the <branch>, if it exists and is the only downstream of <branch>
  (and thus can be slid out immediately following <branch>),
* ``unmanaged``: all local branches that don't appear in the branch layout file,
* ``with-overridden-fork-point``: all local branches that have a :ref:`fork point<fork-point>` override set up
  (even if this override does not affect the location of their fork point anymore).

This command is generally not meant for a day-to-day use, it's mostly needed for the sake of branch name completion in shell.
