.. _github_config_keys:

 .. note::

    git-machete will try to infer the GitHub repository to fire GitHub API requests against ``git remote`` data.
    To override this default behavior and point to the target repository explicitly, you need to set 3 additional, local git config keys:

        1. Remote name ``machete.github.remote``
        2. Organization name ``machete.github.organization``
        3. Repository name ``machete.github.repository``

    You can do it in 2 ways:

        1. Set each key separately with ``git config machete.github.<key_name> "<key_value>"``
        2. Edit config file with ``git config --edit`` and add the keys like its suggested below

            .. code-block:: shell

                [machete "github"]
                    organization = <organization_name>
                    repository = <repo_name>
                    remote = <remote_name>
