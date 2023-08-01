To make it easier to select branch name from the ``status`` output on certain terminals
(like `Alacritty <https://github.com/alacritty/alacritty>`_), you can add an extra space between └─ and ``branch name``
by setting ``git config machete.status.extraSpaceBeforeBranchName true``.

For example, by default the status is displayed as:

.. code-block::

  develop
  │
  ├─feature_branch1
  │
  └─feature_branch2

With ``machete.status.extraSpaceBeforeBranchName`` config set to ``true``:

.. code-block::

   develop
   │
   ├─ feature_branch1
   │
   └─ feature_branch2

..
    Text order in this file is relevant, if you want to change something, find each ``.. include:: status_extraSpaceBeforeBranchName_config_key.rst`` instance
    and if the instance has ``start-line`` or ``end-line`` options provided, make sure that after changes the output text stays the same.
