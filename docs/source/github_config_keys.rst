.. _github_config_keys:

 .. note::

    In order to use custom GitHub repository URL, you need to set 3 additional, local git keys:

        1. Remote name ``machete.github.remote``
        2. Organization name ``machete.github.organization``
        3. Repository name ``machete.github.repository``

    You can do it in 2 ways:

        1. Set each key separately with ``machete.github.<key_name> "<key_value>"``
        2. Edit config file with ``git config --edit`` and add the keys like its suggested below

            .. code-block:: shell

                [machete "github"]
                    organization = <organization_name>
                    repository = <repo_name>
                    remote = <remote_name>
