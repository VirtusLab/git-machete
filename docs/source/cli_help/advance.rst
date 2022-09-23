.. raw:: html

    <style> .green {color:green} </style>

.. role:: green

.. _advance:

advance
-------
**Usage:**

.. code-block:: shell

    git machete advance [-y|--yes]

Fast forwards (as in ``git merge --ff-only``) the current branch ``C`` to match its downstream ``D``, pushes ``C``
and subsequently slides out ``D``. All three steps require manual confirmation unless ``-y/--yes`` is provided.

The downstream ``D`` is selected according to the following criteria:

    * if ``C`` has exactly one downstream (child) branch ``d`` connected with a :green:`green edge` (see help for :ref:`status` for definition) to ``C`` or is overridden, then ``d`` is selected as ``D``,
    * if ``C`` has no downstream branches connected with a :green:`green edge` to ``C``, then ``advance`` fails,
    * if ``C`` has more than one downstream branch connected with a :green:`green edge` to ``C``,
      then user is asked to pick the branch to fast-forward merge into (similarly to what happens in ``git machete go down``). If ``--yes`` is specified, then ``advance`` fails.

As an example, if ``git machete status --color=never --list-commits`` is as follows:

.. code-block::

    master
    |
    m-develop *
      |
      | Enable adding remote branch in the manner similar to git checkout
      o-feature/add-from-remote
        |
        | Add support and sample for machete-post-slide-out hook
        o-feature/post-slide-out-hook

then running ``git machete advance`` will fast-forward the current branch ``develop`` to match ``feature/add-from-remote``, and subsequently slide out the latter.
After ``advance`` completes, ``status`` will show:

.. code-block::

    master
    |
    | Enable adding remote branch in the manner similar to git checkout
    o-develop *
      |
      | Add support and sample for machete-post-slide-out hook
      o-feature/post-slide-out-hook

Note that the current branch after the operation is still ``develop``, just pointing to ``feature/add-from-remote``'s tip now.

**Options:**

-y, --yes         Don't ask for confirmation whether to fast-forward the current branch or whether to slide-out the downstream. Fails if the current branch has more than one :green:`green-edge` downstream branch.
