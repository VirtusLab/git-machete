.. _config:

config
-----
Documentation about available ``git machete`` config keys and environment variables that change the command's default behavior.

Note: ``config`` is not a command as such, just a help topic (there is no ``git machete config`` command).

**Config keys:**

    * ``machete.github.{remote,organization,repository}``:

        When executing ``git machete github <subcommand>`` command, GitHub API server URL will be inferred from ``git remote``.
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

    * ``machete.overrideForkPoint.<branch>.{to,whileDescendantOf}``

        Executing ``git machete fork-point --override-to=<revision> [<branch>]`` sets up a fork point override for <branch>.
        The override data is stored under ``machete.overrideForkPoint.<branch>.to`` and ``machete.overrideForkPoint.<branch>.whileDescendantOf`` git config keys.

    * ``machete.status.extraSpaceBeforeBranchName``

        To make it easier to select branch name from the ``status`` output on certain terminals
        (e.g. `Alacritty <https://github.com/alacritty/alacritty>`_), you can add an extra
        space between ``└─`` and ``branch name`` by setting ``git config machete.status.extraSpaceBeforeBranchName true``.

        For example, by default it's:

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

    * ``machete.worktree.useTopLevelMacheteFile``

        The default value of this key is ``true``, which means that the path to machete definition file will be ``.git/machete``
        for both regular directory and worktree. If you want the worktree to have its own machete definition file (located under
        ``.git/worktrees/.../machete``), set ``git config machete.worktree.useTopLevelMacheteFile false``.

**Environment variables:**

    * ``GIT_MACHETE_EDITOR``

        Name of the editor used by ``git machete e[dit]``, example: ``vim`` or ``nano``.

    * ``GIT_MACHETE_REBASE_OPTS``

        Used to pass extra options to the underlying ``git rebase`` invocation (called by the executed command, such as: ``reapply``, ``slide-out``, ``traverse``, ``update``)
        Example: ``GIT_MACHETE_REBASE_OPTS="--keep-empty --rebase-merges" git machete update``.

    * ``GITHUB_TOKEN``

        Used to store GitHub API token. Used by commands such as: ``anno``, ``clean``, ``github``.
