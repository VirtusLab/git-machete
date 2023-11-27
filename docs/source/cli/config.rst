.. _config:

config
======
Documentation about available ``git machete`` git config keys and environment variables that change the command's default behavior.

Note: ``config`` is not a command as such, just a help topic (there is no ``git machete config`` command).

**Git config keys:**

``machete.github.annotateWithUrls``:
  .. include:: github_annotateWithUrls_config_key.rst

``machete.github.{domain,remote,organization,repository}``:
  .. include:: github_access_config_keys.rst
      :start-line: 3

``machete.overrideForkPoint.<branch>.to``:
    Executing ``git machete fork-point --override-to[-parent|-inferred|=<revision>] [<branch>]`` sets up a fork point override for ``<branch>``.

    The override data is stored under ``machete.overrideForkPoint.<branch>.to`` git config key.

    There should be **no** need for the user to interact with this key directly,
    ``git machete fork-point`` with flags should be used instead.

``machete.status.extraSpaceBeforeBranchName``:
    .. include:: status_extraSpaceBeforeBranchName_config_key.rst

``machete.traverse.push``:
    .. include:: traverse_push_config_key.rst

``machete.worktree.useTopLevelMacheteFile``:
    The default value of this key is ``true``, which means that the path to branch layout file will be ``.git/machete``
    for both regular directory and worktree.

    If you want the worktree to have its own branch layout file (located under ``.git/worktrees/.../machete``),
    set ``git config machete.worktree.useTopLevelMacheteFile false``.


**Environment variables:**

``GIT_MACHETE_EDITOR``
    Name of the editor used by ``git machete e[dit]``, example: ``vim`` or ``nano``.

``GIT_MACHETE_REBASE_OPTS``
    Used to pass extra options to the underlying ``git rebase`` invocation (called by the executed command,
    such as: ``reapply``, ``slide-out``, ``traverse``, ``update``).
    Example: ``GIT_MACHETE_REBASE_OPTS="--keep-empty --rebase-merges" git machete update``.

``GITHUB_TOKEN``
    Used to store GitHub API token. Used by commands such as ``anno --sync-github-prs`` and ``github``.
