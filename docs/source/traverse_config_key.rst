.. note::

    To change the behavior of ``git machete traverse`` command so that it doesn't push branches by default,
    you need to set config key ``git config machete.traverse.push false``.
    Configuration key value can be overridden by the presence of the ``--push`` or ``--push-untracked`` flags.

..
    Text order in this file is relevant, if you want to change something, find each ``.. include:: status_config_key.rst`` instance
    and if the instance has ``start-line`` or ``end-line`` options provided, make sure that after changes the output text stays the same.
