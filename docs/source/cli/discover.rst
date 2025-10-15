.. _discover:

discover
========
**Usage:**

.. code-block:: shell

    git machete discover [-C|--checked-out-since=<date>] [-l|--list-commits] [-r|--roots=<branch1>,<branch2>,...] [-y|--yes]

Discovers and displays tree of branch dependencies using a heuristic based on reflogs
and asks whether to overwrite the existing branch layout :ref:`file` with the new discovered tree.
If confirmed with a ``y[es]`` or ``e[dit]`` reply, backs up the current branch layout file (if it exists) as ``$GIT_DIR/machete~``
and saves the new tree under the usual ``$GIT_DIR/machete`` path.
If the reply was ``e[dit]``, additionally an editor is opened (as in: ``git machete`` :ref:`edit`) after saving the new branch layout file.
``discover`` retains the existing branch qualifiers used by ``git machete traverse`` (see help for :ref:`traverse`).

**Options:**

-C, --checked-out-since=<date>   Only consider branches checked out at least once since the given date.
                                 ``<date>`` can be, for example, ``2 weeks ago`` or ``2020-06-01``, as in ``git log --since=<date>``.
                                 If not present, the date is selected automatically so that around 10 branches are included.

-l, --list-commits               When printing the discovered tree, additionally list the messages of commits introduced on each branch
                                 (as in ``git machete status --list-commits``).

-r, --roots=<branch1,...>        Comma-separated list of branches that should be considered roots of trees of branch dependencies.
                                 If not present, ``master`` is assumed to be a root.
                                 Note that certain other branches can also be additionally deemed to be roots as well.

-y, --yes                        Don't ask for confirmation before saving the newly-discovered tree.
                                 Mostly useful in scripts; not recommended for manual use.
