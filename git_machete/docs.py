# ---------------------------------------------------------------------------------------------------------
# Warning: This file is NOT supposed to be edited directly, but instead regenerated via tox -e docs
# ---------------------------------------------------------------------------------------------------------

from typing import Dict

short_docs: Dict[str, str] = {
    "add": "Add a branch to the tree of branch dependencies",
    "advance": "Fast-forward merge one of children to the current branch, push it and then slide out the child",
    "anno": "Manage custom annotations",
    "clean": "Delete untracked and unmanaged branches and also optionally check out user's open GitHub PRs",
    "config": "Display docs for the git machete configuration keys and environment variables",
    "delete-unmanaged": "Delete local branches that are not present in the definition file",
    "diff": "Diff current working directory or a given branch against its computed fork point",
    "discover": "Automatically discover tree of branch dependencies",
    "edit": "Edit the definition file",
    "file": "Display the location of the definition file",
    "fork-point": "Display or override fork point for a branch",
    "format": "Display docs for the format of the definition file",
    "github": "Create, check out and manage GitHub PRs while keeping them reflected in git machete",
    "go": "Check out the branch relative to the position of the current branch, accepts down/first/last/next/root/prev/up argument",
    "help": "Display this overview, or detailed help for a specified command",
    "hooks": "Display docs for the extra hooks added by git machete",
    "is-managed": "Check if the current branch is managed by git machete (mostly for scripts)",
    "list": "List all branches that fall into one of pre-defined categories (mostly for internal use)",
    "log": "Log the part of history specific to the given branch",
    "reapply": "Rebase the current branch onto its computed fork point",
    "show": "Show name(s) of the branch(es) relative to the position of a branch, accepts down/first/last/next/root/prev/up argument",
    "slide-out": "Slide out the current branch and sync its downstream (child) branches with its upstream (parent) branch via rebase or merge",
    "squash": "Squash the unique history of the current branch into a single commit",
    "status": "Display formatted tree of branch dependencies, including info on their sync with upstream branch and with remote",
    "traverse": "Walk through the tree of branch dependencies and rebase, merge, slide out, push and/or pull each branch one by one. By default starts from current branch",
    "update": "Sync the current branch with its upstream (parent) branch via rebase or merge",
    "version": "Display the version and exit"
}


long_docs: Dict[str, str] = {
    "config": """
        Documentation about available `git machete` config keys and environment variables that change the command's default behavior.

        Note: `config` is not a command as such, just a help topic (there is no `git machete config` command).

        <b>Config keys:</b>
        *  `machete.github.{remote,organization,repository}`:

        When executing `git machete github <subcommand>` command, GitHub API server URL will be inferred from `git remote`.
        Note

        GitHub API server URL will be inferred from `git remote`.
        You can override this by setting the following git config keys:
           Remote name
              E.g. `machete.github.remote` = `origin`
           Organization name
              E.g. `machete.github.organization` = `VirtusLab`
           Repository name
              E.g. `machete.github.repository` = `git-machete`

        To do this, run `git config --local --edit` and add the following section:
        <dim>
          [machete "github"]
              organization = <organization_name>
              repository = <repo_name>
              remote = <remote_name>
        </dim>
        *  `machete.overrideForkPoint.<branch>.{to,whileDescendantOf}`

        Executing `git machete fork-point --override-to=<revision> [<branch>]` sets up a fork point override for <branch>.
        The override data is stored under `machete.overrideForkPoint.<branch>.to` and `machete.overrideForkPoint.<branch>.whileDescendantOf` git config keys.
        *  `machete.status.extraSpaceBeforeBranchName`

        To make it easier to select branch name from the `status` output on certain terminals
        (e.g. Alacritty), you can add an extra
        space between `└─` and `branch name` by setting `git config machete.status.extraSpaceBeforeBranchName true`.

        For example, by default it's:
        <dim>
          develop
          │
          ├─feature_branch1
          │
          └─feature_branch2
        </dim>

        With `machete.status.extraSpaceBeforeBranchName` config set to `true`:
        <dim>
          develop
          │
          ├─ feature_branch1
          │
          └─ feature_branch2
        </dim>
        *  `machete.worktree.useTopLevelMacheteFile`

        The default value of this key is `true`, which means that the path to machete definition file will be `.git/machete`
        for both regular directory and worktree. If you want the worktree to have its own machete definition file (located under
        `.git/worktrees/.../machete`), set `git config machete.worktree.useTopLevelMacheteFile false`.

        <b>Environment variables:</b>
           `GIT_MACHETE_EDITOR`
              Name of the editor used by `git machete e[dit]`, example: `vim` or `nano`.
           `GIT_MACHETE_REBASE_OPTS`
              Used to pass extra options to the underlying `git rebase` invocation (called by the executed command, such as: `reapply`, `slide-out`, `traverse`, `update`)
        Example: `GIT_MACHETE_REBASE_OPTS="--keep-empty --rebase-merges" git machete update`.
           `GITHUB_TOKEN`
              Used to store GitHub API token. Used by commands such as: `anno`, `clean`, `github`.
   """,
}
