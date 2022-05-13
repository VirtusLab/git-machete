.. _github_config_keys:

 .. note::

    **git-machete** will try to infer GitHub API server URL from ``git remote``.
    You can override this by setting the following git config keys:
        Remote name
            E.g. ``machete.github.remote`` = ``origin``

        Organization name
            E.g. ``machete.github.organization`` = ``VirtusLab``

        Repository name
            E.g. ``machete.github.repository`` = ``git-machete``

    To do this, run ``git config --local --edit`` and add the following section:

    .. code-block:: ini

        [machete "github"]
            organization = <organization_name>
            repository = <repo_name>
            remote = <remote_name>
