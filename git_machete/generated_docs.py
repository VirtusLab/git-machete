from typing import Dict

# ---------------------------------------------------------------------------------------------------------
# Warning: This file is NOT supposed to be edited directly, but instead regenerated via `tox -e py-docs`
# ---------------------------------------------------------------------------------------------------------

short_docs: Dict[str, str] = {
    "add": "Add a branch to the tree of branch dependencies",
    "advance": "Fast-forward merge one of children to the current branch, push it and then slide out the child",
    "anno": "Manage custom annotations",
    "clean": "Delete untracked and unmanaged branches and also optionally check out user's open GitHub PRs",
    "completion": "Print out completion script for bash/fish/zsh",
    "config": "Display docs for the git machete configuration keys and environment variables",
    "delete-unmanaged": "Delete local branches that are not present in the branch layout file",
    "diff": "Diff current working directory or a given branch against its computed fork point",
    "discover": "Automatically discover tree of branch dependencies",
    "edit": "Edit the branch layout file",
    "file": "Display the location of the branch layout file",
    "fork-point": "Display or override fork point for a branch",
    "format": "Display docs for the format of the branch layout file",
    "github": "Create, check out and manage GitHub PRs while keeping them reflected in git machete",
    "gitlab": "Create, check out and manage GitLab MRs while keeping them reflected in git machete",
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
    "version": "Display the version and exit",
}

long_docs: Dict[str, str] = {
    "add": """
        <b>Usage:</b><b>
           git machete add [-o|--onto=<target-upstream-branch>] [-R|--as-root] [-y|--yes] [<branch>]</b>

        Adds the provided <branch> (or the current branch, if none specified) to the branch layout file.
        If <branch> is provided but no local branch with the given name exists:
           * if a remote branch of the same name exists in exactly one remote,
             then user is asked whether to check out this branch locally (as in `git checkout`),
           * otherwise, user is asked whether it should be created as a new local branch.

        If the branch layout file is empty or `-R/--as-root` is provided, the branch will be added as a root of the tree of branch dependencies.
        Otherwise, the desired upstream (parent) branch can be specified with `-o/--onto`.
        Neither of these options is mandatory, however; if both are skipped, git machete will try to automatically infer the target upstream.
        If the upstream branch can be inferred, the user will be presented with inferred branch and asked to confirm.

        Note: all the effects of `add` (except git branch creation) can as well be achieved by manually editing the branch layout file.

        <b>Options:</b>
           <b>-f</b>, <b>--as-first-child</b>
              Add the given branch as the first (instead of last) child of its parent.
              Cannot be specified together with `-R/--as-root`.
           <b>-o</b>, <b>--onto=<target-upstream-branch></b>
              Specifies the target parent branch to add the given branch onto.
              Cannot be specified together with `-R/--as-root`.
           <b>-R</b>, <b>--as-root</b>
              Add the given branch as a new root (and not onto any other branch).
              Cannot be specified together with `-o/--onto`.
           <b>-y</b>, <b>--yes</b>
              Don't ask for confirmation whether to create the branch or whether to add onto the inferred upstream.
   """,
    "advance": """
        <b>Usage:</b><b>
           git machete advance [-y|--yes]</b>

        Fast forwards (as in `git merge --ff-only`) the current branch `C` to match its downstream `D`, pushes `C`
        and subsequently slides out `D`. All three steps require manual confirmation unless `-y/--yes` is provided.

        The downstream `D` is selected according to the following criteria:
           * if `C` has exactly one downstream (child) branch `d` connected with a <green>green edge</green> (see help for `status`) to `C`
             or is overridden, then `d` is selected as `D`,
           * if `C` has no downstream branches connected with a <green>green edge</green> to `C`, then `advance` fails,
           * if `C` has more than one downstream branch connected with a <green>green edge</green> to `C`,
             then user is asked to pick the branch to fast-forward merge into (similarly to what happens in `git machete go down`).
             If `--yes` is specified, then `advance` fails.

        As an example, if `git machete status --color=never --list-commits` is as follows:
        <dim>
          master
          |
          m-develop *
            |
            | Enable adding remote branch in the manner similar to git checkout
            o-feature/add-from-remote
              |
              | Add support and sample for machete-post-slide-out hook
              o-feature/post-slide-out-hook
        </dim>

        then running `git machete advance` will fast-forward the current branch `develop` to match `feature/add-from-remote`,
        and subsequently slide out the latter.
        After `advance` completes, `status` will show:
        <dim>
          master
          |
          | Enable adding remote branch in the manner similar to git checkout
          o-develop *
            |
            | Add support and sample for machete-post-slide-out hook
            o-feature/post-slide-out-hook
        </dim>

        Note that the current branch after the operation is still `develop`, just pointing to `feature/add-from-remote`'s tip now.

        If the current branch `C` is annotated with `push=no` qualifier, the push is not performed.
        If the downstream branch `D` is annotated with `slide-out=no` qualifier, the slide-out is not performed.
        See help for `traverse` for more details on the qualifiers.

        <b>Options:</b>
           <b>-y</b>, <b>--yes</b>
              Don't ask for confirmation whether to fast-forward the current branch or whether to slide-out the downstream.
              Fails if the current branch has more than one <green>green-edge</green> downstream branch.
   """,
    "anno": """
        <b>Usage:</b><b>
           git machete anno [-b|--branch=<branch>] [<annotation text>]
           git machete anno -H|--sync-github-prs
           git machete anno -L|--sync-gitlab-mrs</b>

        If invoked without any <annotation text>, prints out the custom annotation for the given branch
        (or current branch, if none specified with `-b/--branch`).

        If invoked with a single empty string <annotation text>, like:<b>
           $ git machete anno ''</b>

        then clears the annotation for the current branch (or a branch specified with `-b/--branch`).

        If invoked with `-H`/`--sync-github-prs` (for GitHub) or `-L`/`--sync-gitlab-mrs` (for GitLab),
        annotates the branches based on their corresponding GitHub PR/GitLab MR numbers and authors.
        When the current user is NOT the author of the PR/MR associated with that branch, adds `rebase=no push=no` branch qualifiers used by `git machete traverse`,
        so that you don't rebase or push someone else's PR/MR by accident (see help for `traverse`).
        Any existing annotations (except branch qualifiers) are overwritten for the branches that have an opened PR/MR;
        annotations for the other branches remain untouched.

        See the help for `github` for how to configure GitHub API access.
        TL;DR: `GITHUB_TOKEN` env var or `~/.github-token` file or `gh`/`hub` CLI configs if exist.

        See the help for `gitlab` for how to configure GitLab API access.
        TL;DR: `GITLAB_TOKEN` env var or `~/.gitlab-token` file or `glab` CLI config if exists.For enterprise domains, non-standard URLs etc., check git config keys in either command's help.

        In any other case, sets the annotation for the given/current branch to the given <annotation text>.
        If multiple <annotation text>'s are passed to the command, they are concatenated with a single space.

        Note: `anno` command is able to overwrite the existing branch qualifiers, for example with `git machete anno "rebase=no push=no"`.

        Note: all the effects of `anno` can be always achieved by manually editing the branch layout file.

        <b>Options:</b>
           <b>-b</b>, <b>--branch=<branch></b>
              Branch to set the annotation for.
           <b>-H</b>, <b>--sync-github-prs</b>
              Annotate with GitHub PR numbers and author logins where applicable.
           <b>-L</b>, <b>--sync-gitlab-mrs</b>
              Annotate with GitLab MR numbers and author logins where applicable.
   """,
    "clean": """
        <b>Usage:</b><b>
           git machete clean [-c|--checkout-my-github-prs] [-y|--yes]</b>

        <b>Deprecated.</b> Use `github checkout-prs --mine`, `delete-unmanaged` and `slide-out --removed-from-remote`.

        Synchronizes with the remote repository:
           * if invoked with `-H` or `--checkout-my-github-prs`, checks out open PRs for the current user associated with the GitHub token
             and also traverses the chain of pull requests upwards, adding branches one by one to git-machete and checks them out locally as well,
           * deletes unmanaged branches,
           * deletes untracked managed branches that have no downstream branch.

        No branch will be deleted unless explicitly confirmed by the user (or unless `-y/--yes` option is passed).
        Equivalent of `git machete github sync` if invoked with `-H` or `--checkout-my-github-prs`.See the help for `github` for how to configure GitHub API access.
        TL;DR: `GITHUB_TOKEN` env var or `~/.github-token` file or `gh`/`hub` CLI configs if exist.
        For enterprise domains, non-standard URLs etc., check git config keys in `github` help.

        <b>Options:</b>
           <b>-c</b>, <b>--checkout-my-github-prs</b>
              Checkout your open PRs into local branches.
           <b>-y</b>, <b>--yes</b>
              Don't ask for confirmation when deleting branches from git.

        <b>Environment variables:</b>
           `GITHUB_TOKEN`
              GitHub API token.

   """,
    "completion": """
        <b>Usage:</b><b>
           git machete completion <shell></b>

        where `<shell>` is one of: `bash`, `fish`, `zsh`.

        Prints out completion scripts.

        <b>Supported shells:</b>

        <b>bash</b>

        Put the following into `~/.bashrc` or `~/.bash_profile`:<b>
           eval "$(git machete completion bash)"  # or, if it doesn't work:
           source <(git machete completion bash)</b>

        <b>fish</b>

        Put the following into `~/.config/fish/config.fish`:<b>
           git machete completion fish | source</b>

        <b>zsh</b>

        Put the following into `~/.zshrc`:<b>
           eval "$(git machete completion zsh)"  # or, if it doesn't work:
           source <(git machete completion zsh)</b>
   """,
    "config": """
        Documentation about available `git machete` git config keys and environment variables that change the command's default behavior.

        Note: `config` is not a command as such, just a help topic (there is no `git machete config` command).

        <b>Git config keys:</b>
           `machete.github.{domain,remote,organization,repository}`:

                 GitHub Enterprise domain
              E.g. `git config machete.github.domain git.example.org`

                 Remote name (as in `git remote`)
              E.g. `git config machete.github.remote origin`

                 Organization and repository name
              E.g. `git config machete.github.organization VirtusLab; git config machete.github.repository git-machete`

              Note that you do <b>not</b> need to set all four keys at once.
              For example, in a typical usage of GitHub Enterprise, it should be enough to just set `machete.github.domain`.
              Only `machete.github.organization` and `machete.github.repository` must be specified together.

           `machete.github.annotateWithUrls`:
 
              Setting this config key to `true` will cause all commands that write GitHub PR numbers into annotations
              to not only include PR number and author (if different from the current user), but also the full URL of the PR.

              The affected (sub)commands clearly include `anno --sync-github-prs` and `github anno-prs`,
              but also `github checkout-prs`, `github create-pr`, `github retarget-pr` and `github restack-pr`.

           `machete.github.forceDescriptionFromCommitMessage`:
              Setting this config key to `true` will force `git machete github create-pr` to take PR description
              from the message body of the first unique commit of the branch, even if `.git/info/description` and/or `.github/pull_request_template.md` is present.

           `machete.gitlab.{domain,remote,namespace,project}`:

                 GitLab self-managed domain
              E.g. `git config machete.gitlab.domain git.example.org`

                 Remote name (as in `git remote`)
              E.g. `git config machete.gitlab.remote origin`

                 Namespace and project name
              E.g. `git config machete.gitlab.namespace foo/bar; git config machete.gitlab.project hello-world`

              Note that you do <b>not</b> need to set all four keys at once.
              For example, in a typical usage for GitLab self-managed instance, it should be enough to just set `machete.gitlab.domain`.
              Only `machete.gitlab.namespace` and `machete.gitlab.project` must be specified together.

           `machete.gitlab.annotateWithUrls`:
 
              Setting this config key to `true` will cause all commands that write GitLab MR numbers into annotations
              to not only include MR number and author (if different from the current user), but also the full URL of the MR.

              The affected (sub)commands clearly include `anno --sync-gitlab-mrs` and `gitlab anno-mrs`,
              but also `gitlab checkout-mrs`, `gitlab create-mr`, `gitlab retarget-mr` and `gitlab restack-mr`.

           `machete.gitlab.forceDescriptionFromCommitMessage`:
              Setting this config key to `true` will force `git machete gitlab create-mr` to take MR description
              from the message body of the first unique commit of the branch, even if `.git/info/description` and/or `.gitlab/merge_request_templates/Default.md` is present.

           `machete.overrideForkPoint.<branch>.to`:
 
              Executing `git machete fork-point --override-to[-parent|-inferred|=<revision>] [<branch>]` sets up a fork point override for `<branch>`.

              The override data is stored under `machete.overrideForkPoint.<branch>.to` git config key.

              There should be <b>no</b> need for the user to interact with this key directly,
              `git machete fork-point` with flags should be used instead.

           `machete.squashMergeDetection`:
 
              Controls the algorithm used to detect squash merges. Possible values are:

                 * `none`: Fastest mode, with no squash merge/rebase detection. Only strict (fast-forward or 2-parent) merges are detected.

                 * `simple` (default): Compares the tree (files & directories in the commit) of the downstream branch with the trees of the upstream branch.
                   This detects squash merges/rebases as long as there exists a squash/rebase commit in the upstream that has the identical tree to what's in the downstream branch.

                 * `exact`: Compares the patch (diff introduced by the commits) of the downstream branch with the patches of the upstream branch.
                   This detects squash merges in more cases than `simple` mode.
                   However, it might have a significant performance impact on large repositories as it requires computing patches for commits in the upstream branch.

              This has an impact on:

                 * whether a grey edge is displayed in `status`,

                 * whether `traverse` suggests to slide out the branch.

           `machete.status.extraSpaceBeforeBranchName`:
 
              To make it easier to select branch name from the `status` output on certain terminals
              (like Alacritty), you can add an extra space between └─ and `branch name`
              by setting `git config machete.status.extraSpaceBeforeBranchName true`.

              For example, by default the status is displayed as:

              develop
              │
              ├─feature_branch1
              │
              └─feature_branch2

              With `machete.status.extraSpaceBeforeBranchName` config set to `true`:

              develop
              │
              ├─ feature_branch1
              │
              └─ feature_branch2

           `machete.traverse.push`:
 
              To change the behavior of `git machete traverse` command so that it doesn't push branches by default,
              you need to set config key `git config machete.traverse.push false`.

              Configuration key value can be overridden by the presence of the `--push` or `--push-untracked` flags.

           `machete.worktree.useTopLevelMacheteFile`:
 
              The default value of this key is `true`, which means that the path to branch layout file will be `.git/machete`
              for both regular directory and worktree.

              If you want the worktree to have its own branch layout file (located under `.git/worktrees/.../machete`),
              set `git config machete.worktree.useTopLevelMacheteFile false`.

        <b>Environment variables:</b>
           `GIT_MACHETE_EDITOR`
              Name of the editor used by `git machete e[dit]`, example: `vim` or `nano`.

           `GIT_MACHETE_REBASE_OPTS`
              Used to pass extra options to the underlying `git rebase` invocation (called by the executed command,
              such as: `reapply`, `slide-out`, `traverse`, `update`).
              Example: `GIT_MACHETE_REBASE_OPTS="--keep-empty --rebase-merges" git machete update`.

           `GITHUB_TOKEN`
              Used to store GitHub API token. Used by commands such as `anno --sync-github-prs` and `github`.

           `GITLAB_TOKEN`
              Used to store GitLab API token. Used by commands such as `anno --sync-gitlab-prs` and `gitlab`.

   """,
    "delete-unmanaged": """
        <b>Usage:</b><b>
           git machete delete-unmanaged [-y|--yes]</b>

        Goes one-by-one through all the local git branches that don't exist in the branch layout file,
        and ask to delete each of them (with `git branch -d` or `git branch -D`) if confirmed by user.
        No branch will be deleted unless explicitly confirmed by the user (or unless `-y/--yes` option is passed).

        Note: this should be used with care since deleting local branches can sometimes make it impossible
        for `git machete` to properly figure out fork points.
        See help for `fork-point` for more details.

        <b>Options:</b>
           <b>-y</b>, <b>--yes</b>
              Don't ask for confirmation.
   """,
    "diff": """
        <b>Usage:</b><b>
           git machete d[iff] [-s|--stat] [<branch>]</b>

        Runs `git diff` of the given branch tip against its fork point or, if none specified,
        of the current working tree against the fork point of the currently checked out branch.
        See help for `fork-point` for more details on the meaning of fork point.

        Note: the branch in question does not need to occur in the branch layout file.

        <b>Options:</b>
           <b>-s</b>, <b>--stat</b>
              Makes `git machete diff` pass `--stat` option to `git diff`, so that only summary (diffstat) is printed.
   """,
    "discover": """
        <b>Usage:</b><b>
           git machete discover [-C|--checked-out-since=<date>] [-l|--list-commits] [-r|--roots=<branch1>,<branch2>,...] [-y|--yes]</b>

        Discovers and displays tree of branch dependencies using a heuristic based on reflogs
        and asks whether to overwrite the existing branch layout `file` with the new discovered tree.
        If confirmed with a `y[es]` or `e[dit]` reply, backs up the current branch layout file (if it exists) as `$GIT_DIR/machete~`
        and saves the new tree under the usual `$GIT_DIR/machete` path.
        If the reply was `e[dit]`, additionally an editor is opened (as in: `git machete` `edit`) after saving the new branch layout file.
        `discover` retains the existing branch qualifiers used by `git machete traverse` (see help for `traverse`).

        <b>Options:</b>
           <b>-C</b>, <b>--checked-out-since=<date></b>
              Only consider branches checked out at least once since the given date.
              `<date>` can be, for example, `2 weeks ago` or `2020-06-01`, as in `git log --since=<date>`.
              If not present, the date is selected automatically so that around 10 branches are included.
           <b>-l</b>, <b>--list-commits</b>
              When printing the discovered tree, additionally lists the messages of commits introduced on each branch
              (as for `git machete status`).
           <b>-r</b>, <b>--roots=<branch1,...></b>
              Comma-separated list of branches that should be considered roots of trees of branch dependencies.
              If not present, `master` is assumed to be a root. Note that in the process of discovery,
              certain other branches can also be additionally deemed to be roots as well.
           <b>-y</b>, <b>--yes</b>
              Don't ask for confirmation before saving the newly-discovered tree.
              Mostly useful in scripts; not recommended for manual use.
   """,
    "edit": """
        <b>Usage:</b><b>
           git machete e[dit]</b>

        Opens an editor and lets you edit the branch layout file manually.

        The editor is determined by checking up the following locations:
           * `$GIT_MACHETE_EDITOR`
           * `$GIT_EDITOR`
           * `$(git config core.editor)`
           * `$VISUAL`
           * `$EDITOR`
           * `editor`
           * `nano`
           * `vi`

        and selecting the first one that is defined and points to an executable file accessible on `PATH`.

        Note that the above editor selection only applies for editing the branch layout file,
        but not for any other actions that may be indirectly triggered by git machete, including editing of rebase TODO list, commit messages etc.

        The branch layout file can be always accessed and edited directly under the path returned by `git machete file`
        (usually `.git/machete`, unless worktrees or submodules are involved).

        <b>Environment variables:</b>
           `GIT_MACHETE_EDITOR`
              Name of the editor executable.

   """,
    "file": """
        <b>Usage:</b><b>
           git machete file</b>

        Outputs the absolute path of branch layout file.
        The file is always called `machete` and is located in the git directory of the project.

        Three cases are possible:
           * if `git machete` is executed from a regular working directory (not a worktree or submodule),
             the file is located under `.git/machete`,
           * if `git machete` is executed from a <b>worktree</b>,
             the file path depends on the `machete.worktree.useTopLevelMacheteFile` config key value:
              - if `machete.worktree.useTopLevelMacheteFile` is true (default), the file is located under `.git/machete`
              - if `machete.worktree.useTopLevelMacheteFile` is false, the file is located under `.git/worktrees/.../machete`,
           * if `git machete` is executed from a <b>submodule</b>, this file is located in the git folder of the submodule itself under `.git/modules/.../machete`.
   """,
    "fork-point": """
        <b>Usage:</b><b>
           git machete fork-point [--inferred] [<branch>]
           git machete fork-point --override-to=<revision>|--override-to-inferred|--override-to-parent [<branch>]
           git machete fork-point --unset-override [<branch>]</b>

        Note: in all three forms, if no `<branch>` is specified, the currently checked out branch is assumed.
        The branch in question does not need to occur in the branch layout file.

        Without any option, `git machete fork-point` displays full hash of the fork point commit for the `<branch>`.
        Fork point of the given `<branch>` is the commit at which the history of the `<branch>` diverges from history of any other branch.

        Fork point is assumed by many `git machete` commands as the place where the unique history of the `<branch>` starts.
        The range of commits between the fork point and the tip of the given branch is, for instance:
           * listed for each branch by `git machete status --list-commits`
           * passed to `git rebase` by `git machete` `reapply`/`slide-out`/`traverse`/`update`
           * provided to `git diff`/`log` by `git machete` `diff`/`log`.

        `git machete` assumes fork point of `<branch>` is the most recent commit in the log of `<branch>` that has NOT been introduced on that very branch,
        but instead occurs on a reflog (see help for `git reflog`) of some other branch.
        This yields a correct result in typical cases, but there are some situations
        (esp. when some local branches have been deleted) where the fork point might not be determined correctly.
        Thus, all rebase-involving operations (`reapply`, `slide-out`, `traverse` and `update`) run `git rebase` in the interactive mode by default,
        unless told explicitly not to do so by `--no-interactive-rebase` flag. This way, the suggested commit range can be inspected before the rebase starts.
        Also, `reapply`, `slide-out`, `squash`, and `update` allow to specify the fork point explicitly by a command-line option.

        `git machete fork-point` is different (and more powerful) than `git merge-base --fork-point`,
        since the latter takes into account only the reflog of the one provided upstream branch,
        while the former scans reflogs of all local branches and their remote tracking branches.
        This makes git machete's `fork-point` more resilient to modifications of `.git/machete` `file` when certain branches are re-attached under new parents (upstreams).

        With `--override-to=<revision>`, sets up a fork point override for `<branch>`.
        Fork point for `<branch>` will be overridden to the provided <revision> (commit) as long as the `<branch>` still points to (or is descendant of) that commit.
        The override data is stored under `machete.overrideForkPoint.<branch>.to` git config key.
        Note: the provided fork point `<revision>` must be an ancestor of the current `<branch>` commit.

        With `--override-to-parent`, overrides fork point of the `<branch>` to the commit currently pointed by `<branch>`'s parent in the branch dependency tree.
        Note: this will only work if `<branch>` has a parent at all (is not a root branch) and parent of `<branch>` is an ancestor of current `<branch>` commit.

        With `--inferred`, displays the commit that `git machete fork-point` infers to be the fork point of `<branch>`.
        If there is NO fork point override for `<branch>`, this is identical to the output of `git machete fork-point`.
        If there is a fork point override for `<branch>`, this is identical to the what the output of `git machete fork-point` would be if the override was NOT present.

        With `--override-to-inferred` option, overrides fork point of the `<branch>` to the commit that `git machete fork-point` infers to be the fork point of `<branch>`.
        Note: this piece of information is also displayed by `git machete status --list-commits` in case a <yellow>yellow</yellow> edge occurs.

        With `--unset-override`, the fork point override for `<branch>` is unset.
        This is simply done by removing the corresponding `machete.overrideForkPoint.<branch>.to` config entry.

        Note: if an overridden fork point applies to a branch `B`, then it's considered to be connected with a <green>green</green> edge to its upstream (parent) `U`,
        even if the overridden fork point of `B` is NOT equal to the commit pointed by `U`.
   """,
    "format": """
        Note: there is no `git machete format` command as such; `format` is just a topic of `git machete help`.

        The format of the branch layout file should be as follows:
        <dim>
          develop
              adjust-reads-prec PR #234 rebase=no push=no
                  block-cancel-order PR #235 rebase=no
                      change-table
                          drop-location-type
              edit-margin-not-allowed
                  full-load-gatling push=no
              grep-errors-script
          master
              hotfix/receipt-trigger PR #236
        </dim>

        In the above example `develop` and `master` are roots of the tree of branch dependencies.
        Branches `adjust-reads-prec`, `edit-margin-not-allowed` and `grep-errors-script` are direct downstream branches for `develop`.
        `block-cancel-order` is a downstream branch of `adjust-reads-prec`, `change-table` is a downstream branch of `block-cancel-order` and so on.

        Every branch name can be followed (after a single space as a delimiter) by a custom annotation, for example `PR #234 rebase=no push=no`, `PR #235 rebase=no` or `push=no`.
        These annotations might contain branch qualifiers (`push=no`, `rebase=no`, `slide-out=no`) that control the behavior of `traverse` (see help for `traverse`).
        Also see help for `anno` command.

        Tabs or any number of spaces can be used as indentation.
        It's only important to use indentation characters consistently between all lines.
   """,
    "github": """
        <b>Usage:</b><b>
           git machete github <subcommand></b>

        where `<subcommand>` is one of: `anno-prs`, `checkout-prs`, `create-pr`, `retarget-pr`.

        Creates, checks out and manages GitHub PRs while keeping them reflected in branch layout file.

        To allow GitHub API access for private repositories (and also to perform side-effecting actions like opening a PR,
        even in case of public repositories), a GitHub API token with `repo` scope is required, see https://github.com/settings/tokens.
        This will be resolved from the first of:
           * `GITHUB_TOKEN` env var,
           * content of the `.github-token` file in the home directory (`~`),
           * current auth token from the `gh` GitHub CLI,
           * current auth token from the `hub` GitHub CLI.

        GitHub Enterprise domains are supported.

        `GITHUB_TOKEN` is used indiscriminately for any domain, both github.com and Enterprise.

        `gh` and `hub` have their own built-in support for Enterprise domains, which is honored by git-machete.

        `.github-token` can have multiple per-domain entries in the format:
        <dim>
          ghp_mytoken_for_github_com
          ghp_myothertoken_for_git_example_org git.example.org
          ghp_yetanothertoken_for_git_example_com git.example.com
        </dim>See <b>Git config keys</b> below in case the target repository cannot be detected automatically (for example, in case of GitHub Enterprise).

        <b>Subcommands:</b>
           `anno-prs [--with-urls]`:
 
              Annotates the branches based on their corresponding GitHub PR numbers and authors.
              Any existing annotations are overwritten for the branches that have an opened PR; annotations for the other branches remain untouched.
              Equivalent to `git machete anno --sync-github-prs`.

              When the current user is NOT the author of the PR associated with that branch, adds `rebase=no push=no` branch qualifiers used by `git machete traverse`,
              so that you don't rebase or push someone else's PR by accident (see help for `traverse`).

              <b>Options:</b>

                 <b>--with-urls</b>
              Also include full PR URLs in the annotations (rather than just PR number).

           `checkout-prs [--all | --by=<github-login> | --mine | <PR-number-1> ... <PR-number-N>]`:
 
              Check out the head branch of the given pull requests (specified by numbers or by a flag),
              also traverse chain of pull requests upwards, adding branches one by one to git-machete and check them out locally.
              Once the specified pull requests are checked out locally, annotate local branches with corresponding pull request numbers.
              If only one PR has been checked out, then switch the local repository's HEAD to its head branch.

              When the current user is NOT the author of the PR associated with that branch, adds `rebase=no push=no` branch qualifiers used by `git machete traverse`,
              so that you don't rebase or push someone else's PR by accident (see help for `traverse`).

              <b>Options:</b>

                 <b>--all</b>
              Checkout all open PRs.

                 <b>--by=<github-login></b>

              Checkout open PRs authored by the given GitHub user, where `<github-login>` is the GitHub account name.

                 <b>--mine</b>
              Checkout open PRs for the current user associated with the GitHub token.

              <b>Parameters:</b>

              `<PR-number-1> ... <PR-number-N>`    Pull request numbers to checkout.

           `create-pr [--draft] [--title=<title>] [--yes]`:
 
              Creates a PR for the current branch, using the upstream (parent) branch as the PR base.
              Once the PR is successfully created, annotates the current branch with the new PR's number.

              If `.git/info/milestone` file is present, its contents (a single number — milestone id) are used as milestone.
              If `.git/info/reviewers` file is present, its contents (one GitHub login per line) are used to set reviewers.

              The subject of the first unique commit of the branch is used as PR title.
              If `.git/info/description` or `.github/pull_request_template.md` file is present, its contents are used as PR description.
              Otherwise (or if `machete.github.forceDescriptionFromCommitMessage` is set), PR description is taken from message body of the first unique commit of the branch.

              If the newly-created PR is stacked atop another PR, the actual PR description posted to GitHub will be prepended with a section
              listing the entire related chain of PRs.

              <b>Options:</b>

                 <b>--draft</b>
              Create the new PR as a draft.

                 <b>--title=<title></b>

              Set the PR title explicitly (the default is to use the first included commit's message as the title).

                 <b>--yes</b>
              Do not ask for confirmation whether to push the branch.

           `restack-pr`:
 
              Perform the following sequence of actions:

                 * If the PR for the current branch is ready for review, it gets converted to a draft.

                 * The PR is retargeted to its upstream (parent) branch, as in `retarget-pr`.

                 * The branch is (force-)pushed into remote.

                 * If the PR has been converted to draft in step 1, it's reverted to ready for review state.

              The drafting/undrafting is useful in case the GitHub repository has set up CODEOWNERS.
              Draft PRs don't get code owners automatically added as reviewers.

           `retarget-pr [-b|--branch=<branch>] [--ignore-if-missing]`:
 
              Sets the base of the current (or specified) branch's PR to upstream (parent) branch, as seen by git machete (see `git machete show up`).

              If after changing the base the PR ends up stacked atop another PR, the PR description posted to GitHub will be prepended with a section
              listing the entire related chain of PRs.

              This header will be updated or removed accordingly with the subsequent runs of `retarget-pr`.

              <b>Options:</b>

                 <b>-b</b>, <b>--branch=<branch></b>

              Specify the branch for which the associated PR base will be set to its upstream (parent) branch. The current branch is used if the option is absent.

                 <b>--ignore-if-missing</b>

              Ignore errors and quietly terminate execution if there is no PR opened for current (or specified) branch.

           `sync`:
 
              <b>Deprecated.</b> Use `github checkout-prs --mine`, `delete-unmanaged` and `slide-out --removed-from-remote`.

              Synchronizes with the remote repository:

                 * checks out open PRs for the current user associated with the GitHub token and also traverses the chain of pull requests upwards,
                   adding branches one by one to git-machete and checks them out locally as well,

                 * deletes unmanaged branches,

                 * deletes untracked managed branches that have no downstream branch.

        <b>Git config keys:</b>
           `machete.github.{domain,remote,organization,repository}` (all subcommands):
 
              GitHub API server URL will be inferred from `git remote`.
              You can alter the default behavior by setting the following git config keys:

                 GitHub Enterprise domain
              E.g. `git config machete.github.domain git.example.org`

                 Remote name (as in `git remote`)
              E.g. `git config machete.github.remote origin`

                 Organization and repository name
              E.g. `git config machete.github.organization VirtusLab; git config machete.github.repository git-machete`

              Note that you do <b>not</b> need to set all four keys at once.
              For example, in a typical usage of GitHub Enterprise, it should be enough to just set `machete.github.domain`.
              Only `machete.github.organization` and `machete.github.repository` must be specified together.

           `machete.github.annotateWithUrls` (all subcommands):
 
              Setting this config key to `true` will cause all commands that write GitHub PR numbers into annotations
              to not only include PR number and author (if different from the current user), but also the full URL of the PR.

              The affected (sub)commands clearly include `anno --sync-github-prs` and `github anno-prs`,
              but also `github checkout-prs`, `github create-pr`, `github retarget-pr` and `github restack-pr`.

           `machete.github.forceDescriptionFromCommitMessage` (`create-pr` only):
              Setting this config key to `true` will force `git machete github create-pr` to take PR description
              from the message body of the first unique commit of the branch, even if `.git/info/description` and/or `.github/pull_request_template.md` is present.

        <b>Environment variables (all subcommands):</b>
           `GITHUB_TOKEN`
              GitHub API token.

   """,
    "gitlab": """
        <b>Usage:</b><b>
           git machete gitlab <subcommand></b>

        where `<subcommand>` is one of: `anno-mrs`, `checkout-mrs`, `create-mr`, `retarget-mr`.

        Creates, checks out and manages GitLab MRs while keeping them reflected in branch layout file.

        To allow GitLab API access for private repositories (and also to perform side-effecting actions like opening a PR,
        even in case of public projects), a GitLab API token with `api` scope is required, see https://gitlab.com/-/user_settings/personal_access_tokens.
        This will be resolved from the first of:
           * `GITLAB_TOKEN` env var,
           * content of the `.gitlab-token` file in the home directory (`~`),
           * current auth token from the `glab` GitLab CLI.

        Self-managed GitLab domains are supported.

        `GITLAB_TOKEN` is used indiscriminately for any domain, both for gitlab.com and a self-managed instance.

        `glab` has its own built-in support for non-gitlab.com domains, which is honored by git-machete.

        `.gitlab-token` can have multiple per-domain entries in the format:
        <dim>
          glpat-mytoken_for_gitlab_com
          glpat-myothertoken_for_git_example_org git.example.org
          glpat-yetanothertoken_for_git_example_com git.example.com
        </dim>See <b>Git config keys</b> below in case the target project cannot be detected automatically (for example, in case of GitLab self-managed instance).

        <b>Subcommands:</b>
           `anno-mrs [--with-urls]`:
 
              Annotates the branches based on their corresponding GitLab MR numbers and authors.
              Any existing annotations are overwritten for the branches that have an opened MR; annotations for the other branches remain untouched.
              Equivalent to `git machete anno --sync-gitlab-mrs`.

              When the current user is NOT the author of the MR associated with that branch, adds `rebase=no push=no` branch qualifiers used by `git machete traverse`,
              so that you don't rebase or push someone else's MR by accident (see help for `traverse`).

              <b>Options:</b>

                 <b>--with-urls</b>
              Also include full MR URLs in the annotations (rather than just MR number).

           `checkout-mrs [--all | --by=<gitlab-login> | --mine | <MR-number-1> ... <MR-number-N>]`:
 
              Check out the source branch of the given pull requests (specified by numbers or by a flag),
              also traverse chain of pull requests upwards, adding branches one by one to git-machete and check them out locally.
              Once the specified pull requests are checked out locally, annotate local branches with corresponding pull request numbers.
              If only one MR has been checked out, then switch the local repository's HEAD to its source branch.

              When the current user is NOT the author of the MR associated with that branch, adds `rebase=no push=no` branch qualifiers used by `git machete traverse`,
              so that you don't rebase or push someone else's MR by accident (see help for `traverse`).

              <b>Options:</b>

                 <b>--all</b>
              Checkout all open MRs.

                 <b>--by=<gitlab-login></b>

              Checkout open MRs authored by the given GitLab user, where `<gitlab-login>` is the GitLab account name.

                 <b>--mine</b>
              Checkout open MRs for the current user associated with the GitLab token.

              <b>Parameters:</b>

              `<MR-number-1> ... <MR-number-N>`    Pull request numbers to checkout.

           `create-mr [--draft] [--title=<title>] [--yes]`:
 
              Creates a MR for the current branch, using the upstream (parent) branch as the MR source branch.
              Once the MR is successfully created, annotates the current branch with the new MR's number.

              If `.git/info/milestone` file is present, its contents (a single number — milestone id) are used as milestone.
              Note that you need to use a global (not per-project) milestone id. Look for something like `Milestone ID: 4489529` on milestone web page.

              If `.git/info/reviewers` file is present, its contents (one GitLab login per line) are used to set reviewers.

              The subject of the first unique commit of the branch is used as MR title.
              If `.git/info/description` or `.gitlab/merge_request_templates/Default.md` file is present, its contents are used as MR description.
              Otherwise (or if `machete.gitlab.forceDescriptionFromCommitMessage` is set), MR description is taken from message body of the first unique commit of the branch.

              If the newly-created MR is stacked atop another MR, the actual MR description posted to GitLab will be prepended with a section
              listing the entire related chain of MRs.

              <b>Options:</b>

                 <b>--draft</b>
              Create the new MR as a draft.

                 <b>--title=<title></b>

              Set the MR title explicitly (the default is to use the first included commit's message as the title).

                 <b>--yes</b>
              Do not ask for confirmation whether to push the branch.

           `restack-mr`:
 
              Perform the following sequence of actions:

                 * If the MR for the current branch is ready for review, it gets converted to a draft.

                 * The MR is retargeted to its upstream (parent) branch, as in `retarget-mr`.

                 * The branch is (force-)pushed into remote.

                 * If the MR has been converted to draft in step 1, it's reverted to ready for review state.

              The drafting/undrafting is useful in case the GitLab project has set up code owners.
              Draft MRs don't get code owners automatically added as reviewers.

           `retarget-mr [-b|--branch=<branch>] [--ignore-if-missing]`:
 
              Sets the target of the current (or specified) branch's MR to upstream (parent) branch, as seen by git machete (see `git machete show up`).

              If after changing the target the MR ends up stacked atop another MR, the MR description posted to GitLab will be prepended with a section
              listing the entire related chain of MRs.

              This header will be updated or removed accordingly with the subsequent runs of `retarget-mr`.

              <b>Options:</b>

                 <b>-b</b>, <b>--branch=<branch></b>

              Specify the branch for which the associated MR source branch will be set to its upstream (parent) branch. The current branch is used if the option is absent.

                 <b>--ignore-if-missing</b>

              Ignore errors and quietly terminate execution if there is no MR opened for current (or specified) branch.

        <b>Git config keys:</b>
           `machete.gitlab.{domain,remote,namespace,project}` (all subcommands):
 
              GitLab API server URL will be inferred from `git remote`.
              You can alter the default behavior by setting the following git config keys:

                 GitLab self-managed domain
              E.g. `git config machete.gitlab.domain git.example.org`

                 Remote name (as in `git remote`)
              E.g. `git config machete.gitlab.remote origin`

                 Namespace and project name
              E.g. `git config machete.gitlab.namespace foo/bar; git config machete.gitlab.project hello-world`

              Note that you do <b>not</b> need to set all four keys at once.
              For example, in a typical usage for GitLab self-managed instance, it should be enough to just set `machete.gitlab.domain`.
              Only `machete.gitlab.namespace` and `machete.gitlab.project` must be specified together.

           `machete.gitlab.annotateWithUrls` (all subcommands):
 
              Setting this config key to `true` will cause all commands that write GitLab MR numbers into annotations
              to not only include MR number and author (if different from the current user), but also the full URL of the MR.

              The affected (sub)commands clearly include `anno --sync-gitlab-mrs` and `gitlab anno-mrs`,
              but also `gitlab checkout-mrs`, `gitlab create-mr`, `gitlab retarget-mr` and `gitlab restack-mr`.

           `machete.gitlab.forceDescriptionFromCommitMessage` (`create-mr` only):
              Setting this config key to `true` will force `git machete gitlab create-mr` to take MR description
              from the message body of the first unique commit of the branch, even if `.git/info/description` and/or `.gitlab/merge_request_templates/Default.md` is present.

        <b>Environment variables (all subcommands):</b>
           `GITLAB_TOKEN`
              GitLab API token.

   """,
    "go": """
        <b>Usage:</b><b>
           git machete g[o] <direction></b>

        where <direction> is one of: `d[own]`, `f[irst]`, `l[ast]`, `n[ext]`, `p[rev]`, `r[oot]`, `u[p]`

        Checks out the branch specified by the given direction relative to the current branch:
           * `down`:    the direct children/downstream branch of the current branch.
           * `first`:   the first downstream of the root branch of the current branch (like `root` followed by `next`),
             or the root branch itself if the root has no downstream branches.
           * `last`:    the last branch in the branch layout file that has the same root as the current branch;
             can be the root branch itself if the root has no downstream branches.
           * `next`:    the direct successor of the current branch in the branch layout file.
           * `prev`:    the direct predecessor of the current branch in the branch layout file.
           * `root`:    the root of the tree where the current branch is located.
             Note: this will typically be something like `develop` or `master`,
             since all branches are usually meant to be ultimately merged to one of those.
           * `up`:      the direct parent/upstream branch of the current branch.

        Roughly equivalent to `git checkout $(git machete show <direction>)`.
   """,
    "help": """
        <b>Usage:</b><b>
           git machete help [<command>]</b>

        Prints a summary of this tool, or a detailed info on a command if provided.
   """,
    "hooks": """
        As with the standard git hooks, git machete looks for its own specific hooks in `$GIT_DIR/hooks/*` (or `$(git config core.hooksPath)/*`, if set).
        All hooks are executed from the top-level folder of the repository (or top-level folder of worktree/submodule, if applicable).

        Note: `hooks` is not a command as such, just a help topic (there is no `git machete hooks` command).

        <b>Hooks:</b>
           `machete-post-slide-out <new-upstream> <lowest-slid-out-branch> [<new-downstreams>...]`
 
              The hook that is executed after a branch (or possibly multiple branches, in case of `slide-out`)
              is slid out by `advance`, `slide-out` or `traverse`.

              At least two parameters (branch names) are passed to the hook:

                 * <new-upstream> is the upstream of the branch that has been slid out, or in case of multiple branches being slid out
                   — the upstream of the highest slid out branch;

                 * <lowest-slid-out-branch> is the branch that has been slid out, or in case of multiple branches being slid out — the lowest slid out branch;

                 * <new-downstreams> are all the following (possibly zero) parameters, which correspond to all original downstreams
                   of <lowest-slid-out-branch>, now reattached as the downstreams of <new-upstream>.

              Note that this may be zero, one, or multiple branches.

              Note: the hook, if present, is executed:

                 * zero or once during a `advance` execution (depending on whether the slide-out has been confirmed or not),

                 * exactly once during a `slide-out` execution (even if multiple branches are slid out),

                 * zero or more times during `traverse` (every time a slide-out operation is confirmed).

              If the hook returns a non-zero exit code, then an error is raised and the execution of the command is aborted —
              `slide-out` won't attempt rebase of the new downstream branches and `traverse` won't continue the traversal.
              In case of `advance` there is no difference (other than exit code of the entire `advance` command being non-zero),
              since slide-out is the last operation that happens within `advance`.

              Note that non-zero exit code of the hook doesn't cancel the effects of slide-out itself, only the subsequent operations.
              The hook is executed only once the slide-out is complete and can in fact rely on .git/machete file being updated to the new branch layout.

           `machete-pre-rebase <new-base> <fork-point-hash> <branch-being-rebased>`
 
              The hook that is executed before rebase is run during `reapply`, `slide-out`, `traverse` and `update`.
              Note that it is NOT executed by `squash` (despite its similarity to `reapply`), since no rebase is involved in `squash`.

              The parameters are exactly the three revisions that are passed to `git rebase --onto`:

                 * what is going to be the new base for the rebased commits,

                 * what is the fork point — the place where the rebased history diverges from the upstream history,

                 * what branch is rebased.

              If the hook returns a non-zero exit code, an error is raised and the entire rebase is aborted.

              Note: this hook is independent from git's standard `pre-rebase hook`.
              If machete-pre-rebase returns zero, the execution flow continues to `git rebase`, which may also run `pre-rebase hook` if present.
              `machete-pre-rebase` is thus always launched before `pre-rebase`.

           `machete-status-branch <branch-name>`
 
              The hook that is executed for each branch displayed during `discover`, `status` and `traverse`.

              The standard output of this hook is displayed at the end of the line, after branch name, (optionally) custom annotation and
              (optionally) remote sync-ness status. Standard error is ignored. If the hook returns a non-zero exit code, both stdout and stderr
              are ignored, and printing the status continues as usual.

              Note: the hook is always invoked with `ASCII_ONLY` variable passed into the environment.
              If `status` runs in ASCII-only mode (if `--color=auto` and stdout is NOT a terminal, or if `--color=never`),
              then `ASCII_ONLY=true`, otherwise `ASCII_ONLY=false`.

        Please see hook_samples directory in git-machete project for examples.
        An example of using the standard git `post-commit hook` to `git machete add` branches automatically is also included.
   """,
    "is-managed": """
        <b>Usage:</b><b>
           git machete is-managed [<branch>]</b>

        Returns with zero exit code if the given branch (or current branch, if none specified) is <b>managed</b> by git machete (that is, listed in .git/machete).

        Returns with a non-zero exit code in case:
           * the <branch> is provided but isn't managed (or doesn't exist), or
           * the <branch> isn't provided and the current branch isn't managed, or
           * the <branch> isn't provided and there's no current branch (detached HEAD).
   """,
    "list": """
        <b>Usage:</b><b>
           git machete list <category></b>

        where <category> is one of: `addable`, `childless`, `managed`, `slidable`, `slidable-after <branch>`, `unmanaged`, `with-overridden-fork-point`.

        Lists all branches that fall into one of the specified categories:
           * `addable`: all branches (local or remote) than can be added to the branch layout file,
           * `childless`: all managed branches that do not possess child branches,
           * `managed`: all branches that appear in the branch layout file,
           * `slidable`: all managed branches that have an upstream and can be slid out with `slide-out` command
           * `slidable-after <branch>`: the downstream branch of the <branch>, if it exists and is the only downstream of <branch>
             (and thus can be slid out immediately following <branch>),
           * `unmanaged`: all local branches that don't appear in the branch layout file,
           * `with-overridden-fork-point`: all local branches that have a `fork point<fork-point>` override set up
             (even if this override does not affect the location of their fork point anymore).

        This command is generally not meant for a day-to-day use, it's mostly needed for the sake of branch name completion in shell.
   """,
    "log": """
        <b>Usage:</b><b>
           git machete l[og] [<branch>]</b>

        Runs `git log` for the range of commits from tip of the given branch (or current branch, if none specified) back to its fork point.
        See help for `fork-point` for more details on meaning of the fork point.

        Note: the branch in question does not need to occur in the branch layout file.
   """,
    "reapply": """
        <b>Usage:</b><b>
           git machete reapply [-f|--fork-point=<fork-point-commit>]</b>

        Interactively rebase the current branch on the top of its computed fork point.
        The chunk of the history to be rebased starts at the automatically computed fork point of the current branch by default,
        but can also be set explicitly by `--fork-point`.
        See help for `fork-point` for more details on meaning of the fork point.

        Note: the current reapplied branch does not need to occur in the branch layout file.

        Tip: `reapply` can be used for squashing the commits on the current branch to make history more condensed before push to the remote,
        but there is also dedicated `squash` command that achieves the same goal without running `git rebase`.

        <b>Options:</b>
           <b>-f</b>, <b>--fork-point=<fork-point-commit></b>
              Specifies the alternative fork point commit after which the rebased part of history is meant to start.

        <b>Environment variables:</b>
           `GIT_MACHETE_REBASE_OPTS`
              Extra options to pass to the underlying `git rebase` invocation, space-separated.
              Example: `GIT_MACHETE_REBASE_OPTS="--keep-empty --rebase-merges" git machete reapply`.

   """,
    "show": """
        <b>Usage:</b><b>
           git machete show <direction> [<branch>]</b>

        where <direction> is one of: `c[urrent]`, `d[own]`, `f[irst]`, `l[ast]`, `n[ext]`, `p[rev]`, `r[oot]`, `u[p]`
        displayed relative to given <branch>, or the current checked out branch if <branch> is unspecified.

        Outputs name of the branch (or possibly multiple branches, in case of `down`) that is:
           * `current`: the current branch; exits with a non-zero status if none (detached HEAD)
           * `down`:    the direct children/downstream branch of the given branch.
           * `first`:   the first downstream of the root branch of the given branch (like `root` followed by `next`),
             or the root branch itself if the root has no downstream branches.
           * `last`:    the last branch in the branch layout file that has the same root as the given branch; can be the root branch itself
             if the root has no downstream branches.
           * `next`:    the direct successor of the given branch in the branch layout file.
           * `prev`:    the direct predecessor of the given branch in the branch layout file.
           * `root`:    the root of the tree where the given branch is located.
             Note: this will typically be something like `develop` or `master`,
             since all branches are usually meant to be ultimately merged to one of those.
           * `up`:      the direct parent/upstream branch of the given branch.
   """,
    "slide-out": """
        <b>Usage:</b><b>
           git machete slide-out --removed-from-remote [--delete]
           git machete slide-out [-d|--down-fork-point=<down-fork-point-commit>] [--delete]
                                 [-M|--merge] [-n|--no-edit-merge|--no-interactive-rebase]
                                 [<branch> [<branch> [<branch> ...]]]</b>

        Removes the given branch (or multiple branches) from the branch layout.
        If no branch has been specified, current branch is slid out.
        If `--removed-from-remote` is specified, all branches that have been removed from the remote are slid out instead.

        Also, if the last branch in the specified chain of `[<branch> [<branch>]]` had any children,
        these children are synced to the parent of the first specified branch.
        Sync is performed either by rebase (default) or by merge (if `--merge` option passed).

        For example, let's assume the following dependency tree:
        <dim>
          develop
              adjust-reads-prec
                  block-cancel-order
                      change-table
                          drop-location-type
                      add-notification
        </dim>

        After running `git machete slide-out adjust-reads-prec block-cancel-order` the tree will be reduced to:
        <dim>
          develop
              change-table
                  drop-location-type
              add-notification
        </dim>

        and `change-table` and `add-notification` will be rebased onto develop (fork point for this rebase is configurable, see `-d` option below).

        The most common use is to slide out a single branch whose upstream was a `develop`/`master` branch and that has been recently merged.

        The provided branches must form a chain — all of the following conditions must be met:
           * for i=1..N-1, (i+1)-th branch must be the only downstream (child) branch of the i-th branch,
           * all provided branches must have an upstream branch (so, in other words, roots of branch layout cannot be slid out).

        Note: Unless `--delete` is passed, `slide-out` doesn't delete any branches from git, just removes them from the tree of branch dependencies.

        Note: if a child branch is annotated with `rebase=no` qualifier, the rebase is not performed.
        See help for `traverse` for more details on the qualifiers.

        <b>Options:</b>
           <b>-d</b>, <b>--down-fork-point=<down-fork-point-commit></b>
              If updating by rebase, specifies the alternative fork point for downstream branches for the operation.
              `git machete fork-point` overrides for downstream branches are recommended over use of this option.
              See also doc for `--fork-point` option in `git machete help reapply` and `git machete help update`.
              Not allowed if updating by merge.
           <b>--delete</b>
              Delete the branches after sliding them out.
           <b>-M</b>, <b>--merge</b>
              Update the downstream branch by merge rather than by rebase.
           <b>-n</b>
              If updating by rebase, equivalent to `--no-interactive-rebase`.
              If updating by merge, equivalent to `--no-edit-merge`.
           <b>--no-edit-merge</b>
              If updating by merge, skip opening the editor for merge commit message while doing
              `git merge` (that is, pass `--no-edit` flag to the underlying `git merge`).
              Not allowed if updating by rebase.
           <b>--no-interactive-rebase</b>
              If updating by rebase, run `git rebase` in non-interactive mode (without `-i/--interactive` flag).
              Not allowed if updating by merge.
           <b>--removed-from-remote</b>
 
              Slide out managed branches whose remote tracking branches have been deleted and that have no downstreams.
              In other words, this deletes all branches except:

                 * those that are unmanaged,

                 * those that have no remote tracking branch set (unpushed),

                 * those whose remote tracking branches still exist (not deleted remotely),

                 * those that have at least one downstream (child) branch.

        <b>Environment variables:</b>
           `GIT_MACHETE_REBASE_OPTS`
              Extra options to pass to the underlying `git rebase` invocations, space-separated.
              Example: `GIT_MACHETE_REBASE_OPTS="--keep-empty --rebase-merges" git machete slide-out`.

   """,
    "squash": """
        <b>Usage:</b><b>
           git machete squash [-f|--fork-point=<fork-point-commit>]</b>

        Squashes the commits belonging uniquely to the current branch into a single commit.
        The chunk of the history to be squashed starts at the automatically computed fork point of the current branch by default,
        but can also be set explicitly by `--fork-point`.
        See help for `fork-point` for more details on meaning of the fork point.
        The message for the resulting commit is taken from the earliest squashed commit (the commit directly following the fork point).

        To simply squash the most recent N commits, use `--fork-point=HEAD~<N>`,
        for example `git machete squash --fork-point=HEAD~3`.

        Tip: `squash` does NOT run `git rebase` under the hood.
        For more complex scenarios that require rewriting the history of current branch, see `reapply` and `update`.

        <b>Options:</b>
           <b>-f</b>, <b>--fork-point=<fork-point-commit></b>
              Specifies the alternative fork point commit after which the squashed part of history is meant to start.
   """,
    "status": """
        <b>Usage:</b><b>
           git machete s[tatus] [--color=WHEN]
                                [-l|--list-commits] [-L|--list-commits-with-hashes]
                                [--squash-merge-detection=MODE]</b>

        Displays a tree-shaped status of the branches listed in the branch layout file.

        Apart from simply ASCII-formatting the branch layout file, this also:
           * colors the edges between upstream (parent) and downstream (children) branches:
              - <red>red edge</red> means not in sync. The downstream branch is NOT a direct descendant of the upstream branch.
              - <yellow>yellow edge</yellow> means in sync but fork point off. The downstream branch is a direct descendant of the upstream branch,
                but the `fork point<fork-point>` of the downstream branch is NOT equal to the upstream branch.
              - <green>green edge</green> means in sync. The downstream branch is a direct descendant of the upstream branch
                and the fork point of the downstream branch is equal to the upstream branch.
              - grey/dimmed edge means merged. The downstream branch has been merged to the upstream branch,
                detected by commit equivalency (default), or by strict detection of merge commits (if `--no-detect-squash-merges` passed).
           * prints (`untracked`/`ahead of <remote>`/`behind <remote>`/`diverged from [& older than] <remote>`) message if the branch
             is not in sync with its remote counterpart;
           * displays the custom annotations (see help for `format` and `anno`) next to each branch, if present. Annotations might contain underlined branch
             qualifiers (`push=no`, `rebase=no`, `slide-out=no`) that control rebase and push behavior of `traverse` (see help for `traverse`);
           * displays the output of `machete-status-branch hook` (see help for `hooks`), if present;
           * optionally lists commits introduced on each branch if `-l/--list-commits` or `-L/--list-commits-with-hashes` is supplied.

        Name of the currently checked-out branch is underlined (or shown in blue on terminals that don't support underline).

        In case of <yellow>yellow edge</yellow>, use `-l` or `-L` flag to show the exact location of the inferred fork point
        (which indicates, among other things, what range of commits is going to be rebased when the branch is updated).
        The inferred fork point can be always overridden manually, see help for `fork-point`.

        Grey/dimmed edge suggests that the downstream branch can be slid out (see help for `slide-out` and `traverse`).

        Use of colors can be disabled with a `--color` flag set to `never`.
        With `--color=always`, git machete always emits colors.
        With `--color=auto` (the default), it emits colors only when standard output is connected to a terminal.
        When colors are disabled, relation between branches is represented in the following way (not including the hash-comments):
        <dim>
          <branch0>
          |
          o-<branch1> *   # green (in sync with parent; asterisk for the current branch)
          | |
          | x-<branch2>   # red (not in sync with parent)
          |   |
          |   ?-<branch3> # yellow (in sync with parent, but parent is not the fork point)
          |
          m-<branch4>     # grey (merged to parent)
        </dim>

        To make it easier to select branch name from the `status` output on certain terminals
        (like Alacritty), you can add an extra space between └─ and `branch name`
        by setting `git config machete.status.extraSpaceBeforeBranchName true`.

        For example, by default the status is displayed as:
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

        <b>Options:</b>
           <b>--color=WHEN</b>
              Colorize the output; WHEN can be `always`, `auto` (default: colorize only if stdout is a terminal), or `never`.
           <b>-l</b>, <b>--list-commits</b>
              Additionally list the commits introduced on each branch.
           <b>-L</b>, <b>--list-commits-with-hashes</b>
              Additionally list the short hashes and messages of commits introduced on each branch.
           <b>--no-detect-squash-merges</b>
              <b>Deprecated</b>, use `--squash-merge-detection=none` instead.
              Only consider strict (fast-forward or 2-parent) merges, rather than rebase/squash merges,
              when detecting if a branch is merged into its upstream (parent).
           <b>--squash-merge-detection=MODE</b>
              Specify the mode for detection of rebase/squash merges (grey edges).
              `MODE` can be `none` (fastest, no squash merges are detected), `simple` (default) or `exact` (slowest).
              See the below paragraph on `machete.squashMergeDetection` git config key for more details.

        <b>Git config keys:</b>
           `machete.squashMergeDetection`:
 
              Controls the algorithm used to detect squash merges. Possible values are:

                 * `none`: Fastest mode, with no squash merge/rebase detection. Only strict (fast-forward or 2-parent) merges are detected.

                 * `simple` (default): Compares the tree (files & directories in the commit) of the downstream branch with the trees of the upstream branch.
                   This detects squash merges/rebases as long as there exists a squash/rebase commit in the upstream that has the identical tree to what's in the downstream branch.

                 * `exact`: Compares the patch (diff introduced by the commits) of the downstream branch with the patches of the upstream branch.
                   This detects squash merges in more cases than `simple` mode.
                   However, it might have a significant performance impact on large repositories as it requires computing patches for commits in the upstream branch.

              This has an impact on:

                 * whether a grey edge is displayed in `status`,

                 * whether `traverse` suggests to slide out the branch.

           `machete.status.extraSpaceBeforeBranchName`
 
              To make it easier to select branch name from the `status` output on certain terminals
              (like Alacritty), you can add an extra space between └─ and `branch name`
              by setting `git config machete.status.extraSpaceBeforeBranchName true`.

              For example, by default the status is displayed as:

              develop
              │
              ├─feature_branch1
              │
              └─feature_branch2

              With `machete.status.extraSpaceBeforeBranchName` config set to `true`:

              develop
              │
              ├─ feature_branch1
              │
              └─ feature_branch2

   """,
    "traverse": """
        <b>Usage:</b><b>
           git machete t[raverse] [-F|--fetch] [-l|--list-commits] [-M|--merge]
                                  [-n|--no-edit-merge|--no-interactive-rebase] [--[no-]push] [--[no-]push-untracked]
                                  [--return-to=WHERE] [--start-from=WHERE] [--squash-merge-detection=MODE]
                                  [-w|--whole] [-W] [-y|--yes]</b>

        Traverses the branches in the order as they occur in branch layout file.
        By default, `traverse` starts from the current branch.
        This behavior can, however, be customized using options: `--start-from=`, `--whole` or `-w`, `-W`.

        For each branch, the command:
           * detects if the branch is merged (grey edge) to its parent (aka upstream):
              - by commit equivalency (default), or by strict detection of merge commits (if `--no-detect-squash-merges` passed),
              - if so, asks the user whether to <b>slide out</b> the branch from the dependency tree (typically branches are no longer needed after they're merged);
           * otherwise, if the branch has a <red>red</red> or <yellow>yellow</yellow> edge to its parent/upstream (see help for `status`):
              - asks the user whether to <b>rebase</b> (default) or merge (if `--merge` passed) the branch onto into its upstream branch
                — equivalent to `git machete update`;
           * if the branch is not tracked on a remote, is ahead of its remote counterpart, or diverged from the counterpart &
             has newer head commit than the counterpart:
              - asks the user whether to <b>push</b> the branch (possibly with `--force-with-lease` if the branches diverged);
           * otherwise, if the branch diverged from the remote counterpart & has older head commit than the counterpart:
              - asks the user whether to <b>reset</b> (`git reset --keep`) the branch to its remote counterpart
           * otherwise, if the branch is behind its remote counterpart:
              - asks the user whether to <b>pull</b> the branch;
           * and finally, if any of the above operations has been successfully completed:
              - prints the updated `status`.

        By default `traverse` asks if the branch should be pushed. This behavior can, however, be changed with the `machete.traverse.push` configuration key.
        It can also be customized using options: `--[no-]push` or `--[no-]push-untracked` — the order of the flags defines their precedence over each other
        (the one on the right overriding the ones on the left). More on them in the <b>Options</b> section below.

        If the traverse flow is stopped (typically due to merge/rebase conflicts), just run `git machete traverse` after the merge/rebase is finished.
        It will pick up the walk from the current branch.
        Unlike with `git rebase` or `git cherry-pick`, there is no special `--continue` flag, as `traverse` is stateless.
        `traverse` does <b>not</b> keep a state of its own like `git rebase` does in `.git/rebase-apply/`.

        The rebase, push and slide-out behaviors of `traverse` can also be customized for each branch separately using branch qualifiers.
        There are `push=no`, `rebase=no` and `slide-out=no` qualifiers that can be used to opt out of default behavior (rebasing, pushing and sliding the branch out).
        The qualifier can appear anywhere in the annotation, but needs to be separated by a whitespace from any other character, as in: `some_annotation_text rebase=no push=no slide-out=no`.
        Qualifiers can only be overwritten by manually editing `.git/machete` file or modifying it with `git machete e[dit]`, or by updating annotations with `git machete anno`.
        Example machete file with branch qualifiers:
        <dim>
          master
            develop  rebase=no slide-out=no
              my-branch  PR #123
              someone-elses-branch  PR #124 rebase=no push=no
              branch-for-local-experiments  push=no
        </dim>

        Operations like `git machete github anno-prs` (`git machete gitlab anno-mrs`)
        and `git machete github checkout-prs` (`git machete gitlab checkout-mrs`) add `rebase=no push=no` branch qualifiers
        when the current user is NOT the author of the PR/MR associated with that branch.

        <b>Options:</b>
           <b>-F</b>, <b>--fetch</b>
              Fetch the remotes of all managed branches at the beginning of traversal (no `git pull` involved, only `git fetch`).
           <b>-l</b>, <b>--list-commits</b>
              When printing the status, additionally list the messages of commits introduced on each branch.
           <b>-M</b>, <b>--merge</b>
              Update by merge rather than by rebase.
           <b>-n</b>
              If updating by rebase, equivalent to `--no-interactive-rebase`. If updating by merge, equivalent to `--no-edit-merge`.
           <b>--no-detect-squash-merges</b>
              <b>Deprecated</b>, use `--squash-merge-detection=none` instead.
              Only consider strict (fast-forward or 2-parent) merges, rather than rebase/squash merges,
              when detecting if a branch is merged into its upstream (parent).
           <b>--no-edit-merge</b>
              If updating by merge, skip opening the editor for merge commit message while doing `git merge`
              (that is, pass `--no-edit` flag to the underlying `git merge`). Not allowed if updating by rebase.
           <b>--no-interactive-rebase</b>
              If updating by rebase, run `git rebase` in non-interactive mode (without `-i/--interactive` flag).
              Not allowed if updating by merge.
           <b>--no-push</b>
              Do not push any (neither tracked nor untracked) branches to remote, re-enable via `--push`.
           <b>--no-push-untracked</b>
              Do not push untracked branches to remote, re-enable via `--push-untracked`.
           <b>--push</b>
              Push all (both tracked and untracked) branches to remote — default behavior. Default behavior can be changed
              by setting git configuration key `git config machete.traverse.push false`.
              Configuration key value can be overridden by the presence of the flag.
           <b>--push-untracked</b>
              Push untracked branches to remote.
           <b>--return-to=WHERE</b>
              Specifies the branch to return after traversal is successfully completed;
              WHERE can be `here` (the current branch at the moment when traversal starts), `nearest-remaining`
              (nearest remaining branch in case the `here` branch has been slid out by the traversal) or
              `stay` (the default — just stay wherever the traversal stops). Note: when user quits by `q`/`yq`
              or when traversal is stopped because one of git actions fails, the behavior is always `stay`.
           <b>--squash-merge-detection=MODE</b>
              Specifies the mode for detection of rebase/squash merges (grey edges).
              `MODE` can be `none` (fastest, no squash merges are detected), `simple` (default) or `exact` (slowest).
              See the below paragraph on `machete.squashMergeDetection` git config key for more details.
           <b>--start-from=WHERE</b>
              Specifies the branch to start the traversal from; WHERE can be `here`
              (the default — current branch, must be managed by git machete), `root` (root branch of the current branch,
              as in `git machete show root`) or `first-root` (first listed managed branch).
           <b>-w</b>, <b>--whole</b>
              Equivalent to `-n --start-from=first-root --return-to=nearest-remaining`;
              useful for quickly traversing & syncing all branches (rather than doing more fine-grained operations on the
              local section of the branch tree).
           <b>-W</b>
              Equivalent to `--fetch --whole`; useful for even more automated traversal of all branches.
           <b>-y</b>, <b>--yes</b>
              Don't ask for any interactive input, including confirmation of rebase/push/pull. Implies `-n`.

        <b>Environment variables:</b>
           `GIT_MACHETE_REBASE_OPTS`
              Extra options to pass to the underlying `git rebase` invocations, space-separated.
              Example: `GIT_MACHETE_REBASE_OPTS="--keep-empty --rebase-merges" git machete traverse`.

        <b>Git config keys:</b>
           `machete.squashMergeDetection`:
 
              Controls the algorithm used to detect squash merges. Possible values are:

                 * `none`: Fastest mode, with no squash merge/rebase detection. Only strict (fast-forward or 2-parent) merges are detected.

                 * `simple` (default): Compares the tree (files & directories in the commit) of the downstream branch with the trees of the upstream branch.
                   This detects squash merges/rebases as long as there exists a squash/rebase commit in the upstream that has the identical tree to what's in the downstream branch.

                 * `exact`: Compares the patch (diff introduced by the commits) of the downstream branch with the patches of the upstream branch.
                   This detects squash merges in more cases than `simple` mode.
                   However, it might have a significant performance impact on large repositories as it requires computing patches for commits in the upstream branch.

              This has an impact on:

                 * whether a grey edge is displayed in `status`,

                 * whether `traverse` suggests to slide out the branch.

           `machete.traverse.push`
 
              To change the behavior of `git machete traverse` command so that it doesn't push branches by default,
              you need to set config key `git config machete.traverse.push false`.

              Configuration key value can be overridden by the presence of the `--push` or `--push-untracked` flags.

   """,
    "update": """
        <b>Usage:</b><b>
           git machete update [-f|--fork-point=<fork-point-commit>] [-M|--merge] [-n|--no-edit-merge|--no-interactive-rebase]</b>

        Synchronizes the current branch with its upstream (parent) branch either by rebase (default) or by merge (if `--merge` option passed).

        If updating by rebase, interactively rebases the current branch on the top of its upstream (parent) branch.
        The chunk of the history to be rebased starts at the fork point of the current branch, which by default is inferred automatically,
        but can also be set explicitly by `--fork-point`.
        See help for `fork-point` for more details on the meaning of fork point.

        If updating by merge, merges the upstream (parent) branch into the current branch.

        <b>Options:</b>
           <b>-f</b>, <b>--fork-point=<fork-point-commit></b>
              If updating by rebase, specifies the alternative fork point commit after which the rebased
              part of history is meant to start. Not allowed if updating by merge.
           <b>-M</b>, <b>--merge</b>
              Update by merge rather than by rebase.
           <b>-n</b>
              If updating by rebase, equivalent to `--no-interactive-rebase`.
              If updating by merge, equivalent to `--no-edit-merge`.
           <b>--no-edit-merge</b>
              If updating by merge, skip opening the editor for merge commit message while doing `git merge`
              (that is, pass `--no-edit` flag to underlying `git merge`). Not allowed if updating by rebase.
           <b>--no-interactive-rebase</b>
              If updating by rebase, run `git rebase` in non-interactive mode (without `-i/--interactive` flag).
              Not allowed if updating by merge.

        <b>Environment variables:</b>
           `GIT_MACHETE_REBASE_OPTS`
              Extra options to pass to the underlying `git rebase` invocation, space-separated.
              Example: `GIT_MACHETE_REBASE_OPTS="--keep-empty --rebase-merges" git machete update`.

   """,
    "version": """
        <b>Usage:</b><b>
           git machete version</b>

        Prints the version and exits.
   """,
}
