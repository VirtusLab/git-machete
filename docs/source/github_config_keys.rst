.. note::

    GitHub API server URL will be inferred from ``git remote``.
    You can alter the default behavior by setting the following git config keys:

        GitHub Enterprise domain
            E.g. ``git config machete.github.domain git.example.org``

        Remote name (as in ``git remote``)
            E.g. ``git config machete.github.remote origin``

        Organization and repository name
            E.g. ``git config machete.github.organization VirtusLab; git config machete.github.repository git-machete``

    Note that you do **not** need to set all four keys at once.
    For example, in a typical usage of GitHub Enterprise, it should be enough to just set ``machete.github.domain``.
    Only ``machete.github.organization`` and ``machete.github.repository`` must be specified together.

..
    Text order in this file is relevant, if you want to change something, find each occurrence of ``.. include:: github_config_keys.rst``
    and if this occurrence has ``start-line`` or ``end-line`` options provided, make sure that after changes the output text stays the same.
