To change the behavior of ``git machete traverse`` command so that it doesn't push branches by default,
you need to set config key ``git config machete.traverse.push false``.

Configuration key value can be overridden by the presence of the ``--push`` or ``--push-untracked`` flags.
