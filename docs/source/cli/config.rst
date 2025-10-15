.. _config:

config
======
Documentation about available ``git machete`` git config keys and environment variables that change the command's default behavior.

Note: ``config`` is not a command as such, just a help topic (there is no ``git machete config`` command).

**Git config keys:**

``machete.github.{domain,remote,organization,repository}``:
  .. include:: git-config-keys/github_access.rst
      :start-line: 3

``machete.github.annotateWithUrls``:
  .. include:: git-config-keys/github_annotateWithUrls.rst

``machete.github.forceDescriptionFromCommitMessage``:
  .. include:: git-config-keys/github_forceDescriptionFromCommitMessage.rst

``machete.github.prDescriptionIntroStyle``:
  .. include:: git-config-keys/github_prDescriptionIntroStyle.rst

``machete.gitlab.{domain,remote,namespace,project}``:
  .. include:: git-config-keys/gitlab_access.rst
      :start-line: 3

``machete.gitlab.annotateWithUrls``:
  .. include:: git-config-keys/gitlab_annotateWithUrls.rst

``machete.gitlab.forceDescriptionFromCommitMessage``:
  .. include:: git-config-keys/gitlab_forceDescriptionFromCommitMessage.rst

``machete.gitlab.mrDescriptionIntroStyle``:
  .. include:: git-config-keys/gitlab_mrDescriptionIntroStyle.rst

``machete.overrideForkPoint.<branch>.to``:
    Executing ``git machete fork-point --override-to[-parent|-inferred|=<revision>] [<branch>]`` sets up a fork point override for ``<branch>``.

    The override data is stored under ``machete.overrideForkPoint.<branch>.to`` git config key.

    There should be **no** need for the user to interact with this key directly,
    ``git machete fork-point`` with flags should be used instead.

``machete.squashMergeDetection``:
    .. include:: git-config-keys/squashMergeDetection.rst

``machete.status.extraSpaceBeforeBranchName``:
    .. include:: git-config-keys/status_extraSpaceBeforeBranchName.rst

``machete.traverse.fetch.<remote>``:
    .. include:: git-config-keys/traverse_fetch_remote.rst

``machete.traverse.push``:
    .. include:: git-config-keys/traverse_push.rst

``machete.worktree.useTopLevelMacheteFile``:
    The default value of this key is ``true``, which means that the path to branch layout file will be ``.git/machete``
    for both regular directory and worktree.

    If you want the worktree to have its own branch layout file (located under ``.git/worktrees/.../machete``),
    set ``git config machete.worktree.useTopLevelMacheteFile false``.

**Environment variables:**

``GIT_MACHETE_EDITOR``
    Name of the editor used by ``git machete e[dit]``, example: ``vim`` or ``nano``.

``GIT_MACHETE_REBASE_OPTS``
    .. include:: env-vars/git_machete_rebase_opts.rst
    Used by commands such as ``reapply``, ``slide-out``, ``traverse`` and ``update``.

``GITHUB_TOKEN``
    Used to store GitHub API token. Used by commands such as ``anno --sync-github-prs`` and ``github``.

``GITLAB_TOKEN``
    Used to store GitLab API token. Used by commands such as ``anno --sync-gitlab-mrs`` and ``gitlab``.
