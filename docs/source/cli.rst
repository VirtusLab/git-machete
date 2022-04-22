.. highlight:: console

.. _cli:

Command Line Interface
======================

When git-machete is installed, it adds ``machete`` command to ``git``, so it can be called from command line: ``git machete <command> <options>``. git machete comes with a wide variety of customizable commands and in this site you can find their documentation.

git machete commands and help topics:

* :ref:`add`              -- Add a branch to the tree of branch dependencies.
* :ref:`advance`          -- Fast-forward merge one of children to the current branch and then slide out this child
* :ref:`anno`             -- Manage custom annotations
* :ref:`clean`            -- Delete untracked and unmanaged branches and also optionally check out user's open GitHub PRs
* :ref:`delete-unmanaged` -- Delete local branches that are not present in the definition file
* :ref:`diff`             -- Diff current working directory or a given branch against its computed fork point
* :ref:`discover`         -- Automatically discover tree of branch dependencies
* :ref:`edit`             -- Edit the definition file
* :ref:`file`             -- Display the location of the definition file
* :ref:`fork-point`       -- Display or override fork point for a branch
* :ref:`format`           -- Display docs for the format of the definition file
* :ref:`github`           -- Create, check out and manage GitHub PRs while keeping them reflected in git machete
* :ref:`go`               -- Check out the branch relative to the position of the current branch, accepts down/first/last/next/root/prev/up <annotation text>
* :ref:`help`             -- Display this overview, or detailed help for a specified command
* :ref:`hooks`            -- Display docs for the extra hooks added by git machete
* :ref:`is-managed`       -- Check if the current branch is managed by git machete (mostly for scripts)
* :ref:`list`             -- List all branches that fall into one of pre-defined categories (mostly for internal use)
* :ref:`log`              -- Log the part of history specific to the given branch
* :ref:`reapply`          -- Rebase the current branch onto its computed fork point
* :ref:`show`             -- Show name(s) of the branch(es) relative to the position of a branch, accepts down/first/last/next/root/prev/up <annotation text>
* :ref:`slide-out`        -- Slide out the current branch and sync its downstream (child) branches with its upstream (parent) branch via rebase or merge
* :ref:`squash`           -- Squash the unique history of the current branch into a single commit
* :ref:`status`           -- Display formatted tree of branch dependencies, including info on their sync with upstream branch and with remote
* :ref:`traverse`         -- Walk through the tree of branch dependencies and rebase, merge, slide out, push and/or pull each branch one by one
* :ref:`update`           -- Sync the current branch with its upstream (parent) branch via rebase or merge
* :ref:`version`          -- Display the version and exit

To get help via CLI run:

.. code-block:: awk

    git machete help
    git machete help go
    git machete go --help

.. include:: cli_help/add.rst
.. include:: cli_help/advance.rst
.. include:: cli_help/anno.rst
.. include:: cli_help/clean.rst
.. include:: cli_help/delete-unmanaged.rst
.. include:: cli_help/diff.rst
.. include:: cli_help/discover.rst
.. include:: cli_help/edit.rst
.. include:: cli_help/file.rst
.. include:: cli_help/fork-point.rst
.. include:: cli_help/format.rst
.. include:: cli_help/github.rst
.. include:: cli_help/go.rst
.. include:: cli_help/help.rst
.. include:: cli_help/hooks.rst
.. include:: cli_help/is-managed.rst
.. include:: cli_help/list.rst
.. include:: cli_help/log.rst
.. include:: cli_help/reapply.rst
.. include:: cli_help/show.rst
.. include:: cli_help/slide-out.rst
.. include:: cli_help/squash.rst
.. include:: cli_help/status.rst
.. include:: cli_help/traverse.rst
.. include:: cli_help/update.rst
.. include:: cli_help/version.rst
