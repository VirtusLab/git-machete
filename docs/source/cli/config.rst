.. _config:

config
======
Documentation about available ``git machete`` git config keys and environment variables that change the command's default behavior.

Note: ``config`` is not a command as such, just a help topic (there is no ``git machete config`` command).

**Git config keys**

``machete.github.{domain,remote,organization,repository,baseRemote,baseOrganization,baseRepository}``
  .. include:: git-config-keys/github.access.rst

``machete.github.annotateWithUrls``
  .. include:: git-config-keys/github.annotateWithUrls.rst

``machete.github.forceDescriptionFromCommitMessage``
  .. include:: git-config-keys/github.forceDescriptionFromCommitMessage.rst

``machete.github.prDescriptionIntroStyle``
  .. include:: git-config-keys/github.prDescriptionIntroStyle.rst

``machete.github.retrieveOnlyMyPullRequests``
  .. include:: git-config-keys/github.retrieveOnlyMyPullRequests.rst

``machete.gitlab.{domain,remote,namespace,project,baseRemote,baseNamespace,baseProject}``
  .. include:: git-config-keys/gitlab.access.rst

``machete.gitlab.annotateWithUrls``
  .. include:: git-config-keys/gitlab.annotateWithUrls.rst

``machete.gitlab.forceDescriptionFromCommitMessage``
  .. include:: git-config-keys/gitlab.forceDescriptionFromCommitMessage.rst

``machete.gitlab.mrDescriptionIntroStyle``
  .. include:: git-config-keys/gitlab.mrDescriptionIntroStyle.rst

``machete.gitlab.retrieveOnlyMyMergeRequests``
  .. include:: git-config-keys/gitlab.retrieveOnlyMyMergeRequests.rst

``machete.overrideForkPoint.<branch>.to``
    Executing ``git machete fork-point --override-to[-parent|-inferred|=<revision>] [<branch>]`` sets up a fork point override for ``<branch>``.

    The override data is stored under ``machete.overrideForkPoint.<branch>.to`` git config key.

    There should be **no** need for the user to interact with this key directly,
    ``git machete fork-point`` with flags should be used instead.

``machete.squashMergeDetection``
    .. include:: git-config-keys/squashMergeDetection.rst

``machete.status.extraSpaceBeforeBranchName``
    .. include:: git-config-keys/status.extraSpaceBeforeBranchName.rst

    .. include:: git-config-keys/status.extraSpaceBeforeBranchName.example.rst

``machete.traverse.fetch.<remote>``
    .. include:: git-config-keys/traverse.fetch.remote.rst

``machete.traverse.push``
    .. include:: git-config-keys/traverse.push.rst

``machete.traverse.whenBranchNotCheckedOutInAnyWorktree``
    .. include:: git-config-keys/traverse.whenBranchNotCheckedOutInAnyWorktree.rst

``machete.worktree.useTopLevelMacheteFile``
    The default value of this key is ``true``, which means that the path to branch layout file will be ``.git/machete``
    for both regular directory and worktree.

    If you want the worktree to have its own branch layout file (located under ``.git/worktrees/.../machete``),
    set ``git config machete.worktree.useTopLevelMacheteFile false``.

**Environment variables**

``GIT_MACHETE_EDITOR``
    Name of the editor used by ``git machete e[dit]``, example: ``vim`` or ``nano``.

``GIT_MACHETE_REBASE_OPTS``
    .. include:: env-vars/git_machete_rebase_opts.rst
    Used by commands such as ``reapply``, ``slide-out``, ``traverse`` and ``update``.

``GITHUB_TOKEN``
    Used to store GitHub API token. Used by commands such as ``anno --sync-github-prs`` and ``github``.

``GITLAB_TOKEN``
    Used to store GitLab API token. Used by commands such as ``anno --sync-gitlab-mrs`` and ``gitlab``.
