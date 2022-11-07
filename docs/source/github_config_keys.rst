.. note::

    GitHub API server URL will be inferred from ``git remote``.
    You can override this by setting the following git config keys:

        Remote name
            E.g. ``machete.github.remote`` = ``origin``

        Organization name
            E.g. ``machete.github.organization`` = ``VirtusLab``

        Repository name
            E.g. ``machete.github.repository`` = ``git-machete``

    To do this, run ``git config --local --edit`` and add the following section:

    .. code-block::

        [machete "github"]
            organization = <organization_name>
            repository = <repo_name>
            remote = <remote_name>

..
    Text order in this file is relevant, if you want to change something, find each ``.. include:: status_config_key.rst`` instance
    and if the instance has ``start-line`` or ``end-line`` options provided, make sure that after changes the output text stays the same.
