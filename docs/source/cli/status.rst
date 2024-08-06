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
======
**Usage:**

.. code-block:: shell

    git machete s[tatus] [--color=WHEN]
                         [-l|--list-commits] [-L|--list-commits-with-hashes]
                         [--squash-merge-detection=MODE]

Displays a tree-shaped status of the branches listed in the branch layout file.

Apart from simply ASCII-formatting the branch layout file, this also:

* colors the edges between upstream (parent) and downstream (children) branches:

  - :red:`red edge` means *not in sync*. The downstream branch is NOT a direct descendant of the upstream branch.

  - :yellow:`yellow edge` means *in sync but fork point off*. The downstream branch is a direct descendant of the upstream branch,
    but the :ref:`fork point<fork-point>` of the downstream branch is NOT equal to the upstream branch.

  - :green:`green edge` means *in sync*. The downstream branch is a direct descendant of the upstream branch
    and the fork point of the downstream branch is equal to the upstream branch.

  - :grey:`grey/dimmed edge` means *merged*. The downstream branch has been merged to the upstream branch,
    detected by commit equivalency (default), or by strict detection of merge commits (if ``--no-detect-squash-merges`` passed).


* prints (``untracked``/``ahead of <remote>``/``behind <remote>``/``diverged from [& older than] <remote>``) message if the branch
  is not in sync with its remote counterpart;

* displays the custom annotations (see help for :ref:`format` and :ref:`anno`) next to each branch, if present. Annotations might contain underlined branch
  qualifiers (``push=no``, ``rebase=no``, ``slide-out=no``) that control rebase and push behavior of ``traverse`` (see help for :ref:`traverse`);

* displays the output of ``machete-status-branch hook`` (see help for :ref:`hooks`), if present;

* optionally lists commits introduced on each branch if ``-l/--list-commits`` or ``-L/--list-commits-with-hashes`` is supplied.

Name of the currently checked-out branch is underlined (or shown in blue on terminals that don't support underline).

In case of :yellow:`yellow edge`, use ``-l`` or ``-L`` flag to show the exact location of the inferred fork point
(which indicates, among other things, what range of commits is going to be rebased when the branch is updated).
The inferred fork point can be always overridden manually, see help for :ref:`fork-point`.

:grey:`Grey/dimmed edge` suggests that the downstream branch can be slid out (see help for :ref:`slide-out` and :ref:`traverse`).

Use of colors can be disabled with a ``--color`` flag set to ``never``.
With ``--color=always``, git machete always emits colors.
With ``--color=auto`` (the default), it emits colors only when standard output is connected to a terminal.
When colors are disabled, relation between branches is represented in the following way (not including the hash-comments):

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

.. include:: git-config-keys/status_extraSpaceBeforeBranchName.rst

**Options:**

--color=WHEN                      Colorize the output; WHEN can be ``always``, ``auto`` (default: colorize only if stdout is a terminal), or ``never``.

-l, --list-commits                Additionally list the commits introduced on each branch.

-L, --list-commits-with-hashes    Additionally list the short hashes and messages of commits introduced on each branch.

--no-detect-squash-merges         **Deprecated**, use ``--squash-merge-detection=none`` instead.
                                  Only consider *strict* (fast-forward or 2-parent) merges, rather than rebase/squash merges,
                                  when detecting if a branch is merged into its upstream (parent).

--squash-merge-detection=MODE     Specify the mode for detection of rebase/squash merges (grey edges).
                                  ``MODE`` can be ``none`` (fastest, no squash merges are detected), ``simple`` (default) or ``exact`` (slowest).
                                  See the below paragraph on ``machete.squashMergeDetection`` git config key for more details.

**Git config keys:**

``machete.squashMergeDetection``:
    .. include:: git-config-keys/squashMergeDetection.rst

``machete.status.extraSpaceBeforeBranchName``
  .. include:: git-config-keys/status_extraSpaceBeforeBranchName.rst
      :end-line: 3
