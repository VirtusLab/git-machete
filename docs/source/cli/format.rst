.. _format:

format
======
Note: there is no ``git machete format`` command as such; ``format`` is just a topic of ``git machete help``.

The format of the branch layout file should be as follows:

.. code-block::

    develop
        adjust-reads-prec PR #234 rebase=no push=no
            block-cancel-order PR #235 rebase=no
                change-table
                    drop-location-type
        edit-margin-not-allowed
            full-load-gatling push=no
        grep-errors-script
    master
        hotfix/receipt-trigger PR #236

In the above example ``develop`` and ``master`` are roots of the tree of branch dependencies.
Branches ``adjust-reads-prec``, ``edit-margin-not-allowed`` and ``grep-errors-script`` are direct downstream branches for ``develop``.
``block-cancel-order`` is a downstream branch of ``adjust-reads-prec``, ``change-table`` is a downstream branch of ``block-cancel-order`` and so on.

Every branch name can be followed (after a single space as a delimiter) by a custom annotation, for example ``PR #234 rebase=no push=no``, ``PR #235 rebase=no`` or ``push=no``.
These annotations might contain branch qualifiers (``push=no``, ``rebase=no``, ``slide-out=no``) that control the behavior of ``traverse`` (see help for :ref:`traverse`).
Also see help for :ref:`anno` command.

Tabs or any number of spaces can be used as indentation.
It's only important to use indentation characters consistently between all lines.
