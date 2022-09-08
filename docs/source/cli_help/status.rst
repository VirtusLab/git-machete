.. raw:: html

    <style> .green {color:green} </style>
    <style> .grey {color:dimgrey} </style>
    <style> .red {color:red} </style>
    <style> .yellow {color:#FFBF00} </style>

.. role:: green
.. role:: grey
.. role:: red
.. role:: yellow

.. _status:

status
------
**Usage:**

.. code-block:: shell

    git machete s[tatus] [--color=WHEN] [-l|--list-commits] [-L|--list-commits-with-hashes] [--no-detect-squash-merges]

Displays a tree-shaped status of the branches listed in the definition file.

Apart from simply ASCII-formatting the definition file, this also:

    * colors the edges between upstream (parent) and downstream (children) branches:

      - :red:`red edge` means that the downstream branch tip is not a direct descendant of the upstream branch tip,

      - :yellow:`yellow edge` means that the downstream branch tip is a direct descendant of the upstream branch tip,
        but the :ref:`fork point<fork-point>` of the downstream branch is not equal to the upstream branch tip,

      - :green:`green edge` means that the downstream branch tip is a direct descendant of the upstream branch tip
        and the fork point of the downstream branch is equal to the upstream branch tip,

      - :grey:`grey/dimmed edge` means that the downstream branch has been merged to the upstream branch,
        detected by commit equivalency (default), or by strict detection of merge commits (if ``--no-detect-squash-merges`` passed).


    * prints (``untracked``/``ahead of <remote>``/``behind <remote>``/``diverged from [& older than] <remote>``) message if the branch is not in sync with its remote counterpart;

    * displays the custom annotations (see :ref:`format` and :ref:`anno`) next to each branch, if present;

    * displays the output of ``machete-status-branch hook`` (see :ref:`hooks`), if present;

    * optionally lists commits introduced on each branch if ``-l/--list-commits`` or ``-L/--list-commits-with-hashes`` is supplied.

Name of the currently checked-out branch is underlined (or shown in blue on terminals that don't support underline).

In case of :yellow:`yellow edge`, use ``-l`` or ``-L`` flag to show the exact location of the inferred fork point
(which indicates e.g. what range of commits is going to be rebased when the branch is updated).
The inferred fork point can be always overridden manually, see :ref:`fork-point`.

:grey:`Grey/dimmed edge` suggests that the downstream branch can be slid out (see :ref:`slide-out` and :ref:`traverse`).

Using colors can be disabled with a ``--color`` flag set to ``never``.
With ``--color=always``, git machete always emits colors and with ``--color=auto``, it emits colors only when standard output is connected to a terminal.
``--color=auto`` is the default. When colors are disabled, relation between branches is represented in the following way (not including the hash-comments):

.. code-block::

    <branch0>
    |
    o-<branch1> *   # green (in sync with parent; asterisk for the current branch)
    | |
    | x-<branch2>   # red (not in sync with parent)
    |   |
    |   ?-<branch3> # yellow (in sync with parent, but parent is not the fork point)
    |
    m-<branch4>     # grey (merged to parent)


**Options:**

--color=WHEN                      Colorize the output; WHEN can be ``always``, ``auto`` (default; i.e. only if stdout is a terminal), or ``never``.

-l, --list-commits                Additionally list the commits introduced on each branch.

-L, --list-commits-with-hashes    Additionally list the short hashes and messages of commits introduced on each branch.

--no-detect-squash-merges         Only consider *strict* (fast-forward or 2-parent) merges, rather than rebase/squash merges, when detecting if a branch is merged into its upstream (parent).

**Config keys:**

``machete.status.extraSpaceBeforeBranchName``
    .. include:: status_config_key.rst