.. _discover:

discover
--------
**Usage:**

.. code-block:: shell

    git machete discover [-C|--checked-out-since=<date>] [-l|--list-commits] [-r|--roots=<branch1>,<branch2>,...] [-y|--yes]

Discovers and displays tree of branch dependencies using a heuristic based on reflogs and asks whether to overwrite the existing definition
:ref:`file` with the new discovered tree.
If confirmed with a ``y[es]`` or ``e[dit]`` reply, backs up the current definition file (if it exists) as ``$GIT_DIR/machete~``
and saves the new tree under the usual ``$GIT_DIR/machete`` path.
If the reply was ``e[dit]``, additionally an editor is opened (as in: ``git machete`` :ref:`edit`) after saving the new definition file.

**Options:**

-C, --checked-out-since=<date>   Only consider branches checked out at least once since the given date.
                                 <date> can be e.g. ``2 weeks ago`` or ``2020-06-01``, as in ``git log --since=<date>``.
                                 If not present, the date is selected automatically so that around 10 branches are included.

-l, --list-commits               When printing the discovered tree, additionally lists the messages of commits introduced on each branch
                                 (as for ``git machete status``).

-r, --roots=<branch1,...>        Comma-separated list of branches that should be considered roots of trees of branch dependencies.
                                 If not present, ``master`` is assumed to be a root. Note that in the process of discovery,
                                 certain other branches can also be additionally deemed to be roots as well.

-y, --yes                        Don't ask for confirmation before saving the newly-discovered tree.
                                 Mostly useful in scripts; not recommended for manual use.
