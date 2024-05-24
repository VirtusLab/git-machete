.. only:: html
.. highlight:: console

git-machete
-----------

git machete is a robust tool that **simplifies your git workflows**.

The bird's eye view provided by git machete makes **merges/rebases/push/pulls hassle-free**
even when **multiple branches** are present in the repository
(master/develop, your topic branches, teammate's branches checked out for review, etc.).

Using this tool, you can maintain **small, focused, easy-to-review pull requests** with little effort.

A look at a ``git machete status`` gives an instant answer to the questions:

* What branches are in this repository?
* What is going to be merged (rebased/pushed/pulled) and to what?

``git machete traverse`` semi-automatically traverses the branches, helping you effortlessly rebase, merge, push and pull.

When git-machete is installed, it adds ``machete`` command to ``git``, so it can be called from command line: ``git machete <command> <options>``.
git machete comes with a wide variety of customizable commands and in this site you can find their documentation.

git machete commands and help topics:

.. include:: short_docs.rst

.. include:: learning_materials.rst

General options
---------------

--debug           Log detailed diagnostic info, including outputs of the executed git commands.
-h, --help        Print help and exit.
-v, --verbose     Log the executed git commands.
--version         Print version and exit.

Commands & help topics
----------------------

.. include:: cli/add.rst
.. include:: cli/advance.rst
.. include:: cli/anno.rst
.. include:: cli/config.rst
.. include:: cli/clean.rst
.. include:: cli/completion.rst
.. include:: cli/delete-unmanaged.rst
.. include:: cli/diff.rst
.. include:: cli/discover.rst
.. include:: cli/edit.rst
.. include:: cli/file.rst
.. include:: cli/fork-point.rst
.. include:: cli/format.rst
.. include:: cli/github.rst
.. include:: cli/gitlab.rst
.. include:: cli/go.rst
.. include:: cli/help.rst
.. include:: cli/hooks.rst
.. include:: cli/is-managed.rst
.. include:: cli/list.rst
.. include:: cli/log.rst
.. include:: cli/reapply.rst
.. include:: cli/show.rst
.. include:: cli/slide-out.rst
.. include:: cli/squash.rst
.. include:: cli/status.rst
.. include:: cli/traverse.rst
.. include:: cli/update.rst
.. include:: cli/version.rst
