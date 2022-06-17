import textwrap
from typing import Dict
from git_machete.constants import DISCOVER_DEFAULT_FRESH_BRANCH_COUNT

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

github_api_access = '''To allow GitHub API access for private repositories (and also to perform side-effecting actions like opening a PR,
even in case of public repositories), a GitHub API token with `repo` scope is required, see https://github.com/settings/tokens.
This will be resolved from the first of:
    1. `GITHUB_TOKEN` env var,
    2. content of the `.github-token` file in the home directory (`~`),
    3. current auth token from the `gh` GitHub CLI,
    4. current auth token from the `hub` GitHub CLI.'''

github_config_keys = '''GitHub API server URL will be inferred from `git remote`.
You can override this by setting the following local git config keys:
    Remote name
        E.g. `machete.github.remote` = `origin`
    Organization name
        E.g. `machete.github.organization` = `VirtusLab`
    Repository name
        E.g. `machete.github.repository` = `git-machete`

To do this, run `git config --local --edit` and add the following section:
    [machete "github"]
        organization = <organization_name>
        repository = <repo_name>
        remote = <remote_name>'''

status_extraSpaceBeforeBranchName_config_key = '''The default value of this key is `false` but in order to make it easier to select branch
name from the `git machete status` output on certain terminals (e.g. Alacritty), you can add an extra
space between └─ and branch name by setting `git config machete.status.extraSpaceBeforeBranchName true`.

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
    └─ feature_branch2'''

long_docs: Dict[str, str] = {
    "add": """
        <b>Usage: git machete add [-o|--onto=<target-upstream-branch>] [-R|--as-root] [-y|--yes] [<branch>]</b>

        Adds the provided <branch> (or the current branch, if none specified) to the definition file.
        If <branch> is provided but no local branch with the given name exists:
        * if a remote branch of the same name exists in exactly one remote, then user is asked whether to check out this branch locally (as in `git checkout`),
        * otherwise, user is asked whether it should be created as a new local branch.

        If the definition file is empty or `-R`/`--as-root` is provided, the branch will be added as a root of the tree of branch dependencies.
        Otherwise, the desired upstream (parent) branch can be specified with `-o`/`--onto`.
        Neither of these options is mandatory, however; if both are skipped, git machete will try to automatically infer the target upstream.
        If the upstream branch can be inferred, the user will be presented with inferred branch and asked to confirm.

        Note: all the effects of `add` (except git branch creation) can as well be achieved by manually editing the definition file.

        <b>Options:</b>
          <b>-o, --onto=<target-upstream-branch></b>    Specifies the target parent branch to add the given branch onto.
                                                 Cannot be specified together with `-R`/`--as-root`.

          <b>-R, --as-root</b>                          Add the given branch as a new root (and not onto any other branch).
                                                 Cannot be specified together with `-o`/`--onto`.

          <b>-y, --yes</b>                              Don't ask for confirmation whether to create the branch or whether to add onto the inferred upstream.
    """,
    "advance": """
        <b>Usage: git machete advance [-y|--yes]</b>

        Fast forwards (as in `git merge --ff-only`) the current branch `C` to match its downstream `D`, pushes `C`
        and subsequently slides out `D`. All three steps require manual confirmation unless `-y`/`--yes` is provided.

        The downstream `D` is selected according to the following criteria:
        * if `C` has exactly one downstream branch `d` whose tip is a descendant of `C`, and whose fork point is equal to `C` or is overridden
          (basically: there's a <b><green>green edge</green></b> between `C` and `d`), then `d` is selected as `D`,
        * if `C` has no downstream branches connected with a <b><green>green edge</green></b> to `C`, then `advance` fails,
        * if `C` has more than one downstream branch connected with a <b><green>green edge</green></b> to `C`,
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
            | |
            | | Add support and sample for machete-post-slide-out hook
            | o-feature/post-slide-out-hook
            |
            | Remove support for Python 2
            | Remove support for Python 2 - 1st round of fixes
            ?-chore/v3
            |
            | Apply Python2-compatible static typing
            x-feature/types
        </dim>
        then running `git machete advance` will fast-forward the current branch `develop` to match `feature/add-from-remote`, and subsequently slide out the latter.
        After `advance` completes, `status` will show:
        <dim>
          master
          |
          | Enable adding remote branch in the manner similar to git checkout
          o-develop *
            |
            | Add support and sample for machete-post-slide-out hook
            o-feature/post-slide-out-hook
            |
            | Remove support for Python 2
            | Remove support for Python 2 - 1st round of fixes
            ?-chore/v3
            |
            | Apply Python2-compatible static typing
            x-feature/types
        </dim>
        Note that the current branch after the operation is still `develop`, just pointing to `feature/add-from-remote`'s tip now.

        <b>Options:</b>
          <b>-y, --yes</b>         Don't ask for confirmation whether to fast-forward the current branch or whether to slide-out the downstream.
                            Fails if the current branch has more than one green-edge downstream branch.
    """,
    "anno": f"""
        <b>Usage:
          git machete anno [-b|--branch=<branch>] [<annotation text>]
          git machete anno -H|--sync-github-prs</b>

        If invoked without any argument, prints out the custom annotation for the given branch (or current branch, if none specified with `-b/--branch`).

        If invoked with a single empty string argument, like:
        <dim>$ git machete anno ''</dim>
        then clears the annotation for the current branch (or a branch specified with `-b/--branch`).

        If invoked with `-H` or `--sync-github-prs`, annotates the branches based on their corresponding GitHub PR numbers and authors.
        Any existing annotations are overwritten for the branches that have an opened PR; annotations for the other branches remain untouched.

{textwrap.indent(github_api_access, "          ")}

{textwrap.indent(github_config_keys, "          ")}

        In any other case, sets the annotation for the given/current branch to the given argument.
        If multiple arguments are passed to the command, they are concatenated with a single space.

        Note: all the effects of `anno` can be always achieved by manually editing the definition file.

        <b>Options:</b>
          <b>-b, --branch=<branch></b>      Branch to set the annotation for.
          <b>-H, --sync-github-prs</b>      Annotate with GitHub PR numbers and authors where applicable.
    """,
    "clean": f"""
        <b>Usage: git machete clean [-c|--checkout-my-github-prs] [-y|--yes]</b>

        Synchronizes with the remote repository:
            1. if invoked with `-H` or `--checkout-my-github-prs`, checks out open PRs for the current user associated with the GitHub token and also traverses the chain of pull requests upwards, adding branches one by one to git-machete and checks them out locally as well,
            2. deletes unmanaged branches,
            3. deletes untracked managed branches that have no downstream branch.

        No branch will be deleted unless explicitly confirmed by the user (or unless `-y/--yes` option is passed).
        Equivalent of `git machete github sync` if invoked with `-H` or `--checkout-my-github-prs`.

{textwrap.indent(github_api_access, "          ")}

{textwrap.indent(github_config_keys, "          ")}

        **Options:**
          <b>--c, --checkout-my-github-prs</b>     Checkout your open PRs into local branches.
          <b>-y, --yes</b>                         Don't ask for confirmation when deleting branches from git.
    """,
    "config": f"""
        <b>Config keys: </b>

        - `machete.github.{{remote,organization,repository}}`:

          When executing `git machete github <subcommand>` command, {textwrap.indent(github_config_keys, "          ").strip()}

        - `machete.overrideForkPoint.<branch>.{{to,whileDescendantOf}}`

          Executing `git machete fork-point --override-to=<revision> [<branch>]` sets up a fork point override for <branch>.
          The override data is stored under `machete.overrideForkPoint.<branch>.to` and `machete.overrideForkPoint.<branch>.whileDescendantOf` git config keys.

        - `machete.status.extraSpaceBeforeBranchName`

          {textwrap.indent(status_extraSpaceBeforeBranchName_config_key, "          ").strip()}

        - `machete.worktree.useTopLevelMacheteFile`

          The default value of this key is `true`, which means that the path to machete definition file will be `.git/machete`
          for both regular directory and worktree. If you want the worktree to have its own machete definition file (located under
          `.git/worktrees/.../machete`), set `git config machete.worktree.useTopLevelMacheteFile false`.


        <b>Environment variables: </b>

        - `GIT_MACHETE_EDITOR`

          Name of the editor used by `git machete e[dit]`, example: `vim` or `nano`.

        - `GIT_MACHETE_REBASE_OPTS`

          Used to pass extra options to the underlying `git rebase` invocation (called by the executed command, such as: `reapply`, `slide-out`, `traverse`, `update`)
          Example: `GIT_MACHETE_REBASE_OPTS="--keep-empty --rebase-merges" git machete update`.

        - `GITHUB_TOKEN`

          Used to store GitHub API token. Used by commands such as: `anno`, `clean`, `github`.
    """,
    "delete-unmanaged": """
        <b>Usage: git machete delete-unmanaged [-y|--yes]</b>

        Goes one-by-one through all the local git branches that don't exist in the definition file,
        and ask to delete each of them (with `git branch -d` or `git branch -D`) if confirmed by user.
        No branch will be deleted unless explicitly confirmed by the user (or unless `-y/--yes` option is passed).

        Note: this should be used with care since deleting local branches can sometimes make it impossible for `git machete` to properly figure out fork points.
        See `git machete help fork-point` for more details.

        <b>Options:</b>
          <b>-y, --yes</b>          Don't ask for confirmation.
    """,
    "diff": """
        <b>Usage: git machete d[iff] [-s|--stat] [<branch>]</b>

        Runs `git diff` of the given branch tip against its fork point or, if none specified, of the current working tree against the fork point of the currently checked out branch.
        See `git machete help fork-point` for more details on meaning of the "fork point".

        Note: the branch in question does not need to occur in the definition file.

        Options:
          <b>-s, --stat</b>    Makes `git machete diff` pass `--stat` option to `git diff`, so that only summary (diffstat) is printed.
    """,
    "discover": f"""
        <b>Usage: git machete discover [-C|--checked-out-since=<date>] [-l|--list-commits] [-r|--roots=<branch1>,<branch2>,...] [-y|--yes]</b>

        Discovers and displays tree of branch dependencies using a heuristic based on reflogs and asks whether to overwrite the existing definition file with the new discovered tree.
        If confirmed with a `y[es]` or `e[dit]` reply, backs up the current definition file (if it exists) as `$GIT_DIR/machete~` and saves the new tree under the usual `$GIT_DIR/machete` path.
        If the reply was `e[dit]`, additionally an editor is opened (as in `git machete edit`) after saving the new definition file.

        Options:
          <b>-C, --checked-out-since=<date></b>   Only consider branches checked out at least once since the given date. <date> can be e.g. `2 weeks ago` or `2020-06-01`, as in `git log --since=<date>`.
                                           If not present, the date is selected automatically so that around {str(DISCOVER_DEFAULT_FRESH_BRANCH_COUNT)} branches are included.

          <b>-l, --list-commits</b>               When printing the discovered tree, additionally lists the messages of commits introduced on each branch (as for `git machete status`).

          <b>-r, --roots=<branch1,...></b>        Comma-separated list of branches that should be considered roots of trees of branch dependencies.
                                           If not present, `master` is assumed to be a root.
                                           Note that in the process of discovery, certain other branches can also be additionally deemed to be roots as well.

          <b>-y, --yes</b>                        Don't ask for confirmation before saving the newly-discovered tree.
                                           Mostly useful in scripts; not recommended for manual use.
    """,
    "edit": """
        <b>Usage: git machete e[dit]</b>

        Opens an editor and lets you edit the definition file manually.

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

        Note that the above editor selection only applies for editing the definition file,
        but not for any other actions that may be indirectly triggered by git-machete, including editing of rebase TODO list, commit messages etc.

        The definition file can be always accessed and edited directly under the path returned by `git machete file` (currently fixed to <git-directory>/machete).
    """,
    "file": """
        <b>Usage: git machete file</b>

        Outputs the absolute path of machete definition file.
        The file is always called `machete` and is located in the git directory of the project.

        Three cases are possible:
        * if `git machete` is executed from a regular working directory (not a worktree or submodule), the file is located under `.git/machete`,
        * if `git machete` is executed from a <b>worktree</b>, the file path depends on the `machete.worktree.useTopLevelMacheteFile` config key value:
          * if `machete.worktree.useTopLevelMacheteFile` is true (default), the file is located under `.git/machete`
          * if `machete.worktree.useTopLevelMacheteFile` is false, the file is located under `.git/worktrees/.../machete`,
        * if `git machete` is executed from a <b>submodule</b>, this file is located in the git folder of the submodule itself under `.git/modules/.../machete`.
    """,
    "fork-point": """
        <b>Usage:
          git machete fork-point [--inferred] [<branch>]
          git machete fork-point --override-to=<revision>|--override-to-inferred|--override-to-parent [<branch>]
          git machete fork-point --unset-override [<branch>]</b>

        Note: in all three forms, if no <branch> is specified, the currently checked out branch is assumed.
        The branch in question does not need to occur in the definition file.


        Without any option, displays full hash of the fork point commit for the <branch>.
        Fork point of the given <branch> is the commit at which the history of the <branch> diverges from history of any other branch.

        Fork point is assumed by many `git machete` commands as the place where the unique history of the <branch> starts.
        The range of commits between the fork point and the tip of the given branch is, for instance:
        * listed for each branch by `git machete status --list-commits`
        * passed to `git rebase` by `git machete reapply`/`slide-out`/`traverse`/`update`
        * provided to `git diff`/`log` by `git machete diff`/`log`.

        `git machete` assumes fork point of <branch> is the most recent commit in the log of <branch> that has NOT been introduced on that very branch,
        but instead occurs on a reflog (see help for `git reflog`) of some other, usually chronologically earlier, branch.
        This yields a correct result in typical cases, but there are some situations
        (esp. when some local branches have been deleted) where the fork point might not be determined correctly.
        Thus, all rebase-involving operations (`reapply`, `slide-out`, `traverse` and `update`) run `git rebase` in the interactive mode by default,
        unless told explicitly not to do so by `--no-interactive-rebase` flag, so that the suggested commit range can be inspected before the rebase commences.
        Also, `reapply`, `slide-out`, `squash`, and `update` allow to specify the fork point explicitly by a command-line option.

        `git machete fork-point` is different (and more powerful) than `git merge-base --fork-point`,
        since the latter takes into account only the reflog of the one provided upstream branch,
        while the former scans reflogs of all local branches and their remote tracking branches.
        This makes git-machete's `fork-point` more resilient to modifications of .git/machete file where certain branches are re-attached under new parents (upstreams).


        With `--override-to=<revision>`, sets up a fork point override for <branch>.
        Fork point for <branch> will be overridden to the provided <revision> (commit) as long as the <branch> still points to (or is descendant of) the commit X
        that <branch> pointed to at the moment the override is set up.
        Even if revision is a symbolic name (e.g. other branch name or `HEAD~3`) and not explicit commit hash (like `a1b2c3ff`),
        it's still resolved to a specific commit hash at the moment the override is set up (and not later when the override is actually used).
        The override data is stored under `machete.overrideForkPoint.<branch>.to` and `machete.overrideForkPoint.<branch>.whileDescendantOf` git config keys.
        Note: the provided fork point <revision> must be an ancestor of the current <branch> commit X.

        With `--override-to-parent`, overrides fork point of the <branch> to the commit currently pointed by <branch>'s parent in the branch dependency tree.
        Note: this will only work if <branch> has a parent at all (i.e. is not a root) and parent of <branch> is an ancestor of current <branch> commit X.

        With `--inferred`, displays the commit that `git machete fork-point` infers to be the fork point of <branch>.
        If there is NO fork point override for <branch>, this is identical to the output of `git machete fork-point`.
        If there is a fork point override for <branch>, this is identical to the what the output of `git machete fork-point` would be if the override was NOT present.

        With `--override-to-inferred` option, overrides fork point of the <branch> to the commit that `git machete fork-point` infers to be the fork point of <branch>.
        Note: this piece of information is also displayed by `git machete status --list-commits` in case a <b><yellow>yellow edge</yellow></b> occurs.

        With `--unset-override`, the fork point override for <branch> is unset.
        This is simply done by removing the corresponding `machete.overrideForkPoint.<branch>.*` config entries.


        <b>Note:</b> if an overridden fork point applies to a branch `B`, then it's considered to be connected with a <b><green>green edge</green></b> to its upstream (parent) `U`,
        even if the overridden fork point of `B` is NOT equal to the commit pointed by `U`.
    """,
    "format": """
        Note: there is no 'git machete format' command as such; 'format' is just a topic of 'git machete help'.

        The format of the definition file should be as follows:
        <dim>
          develop
              adjust-reads-prec PR #234
                  block-cancel-order PR #235
                      change-table
                          drop-location-type
              edit-margin-not-allowed
                  full-load-gatling
              grep-errors-script
          master
              hotfix/receipt-trigger PR #236
        </dim>
        In the above example `develop` and `master` are roots of the tree of branch dependencies.
        Branches `adjust-reads-prec`, `edit-margin-not-allowed` and `grep-errors-script` are direct downstream branches for `develop`.
        `block-cancel-order` is a downstream branch of `adjust-reads-prec`, `change-table` is a downstream branch of `block-cancel-order` and so on.

        Every branch name can be followed (after a single space as a delimiter) by a custom annotation - a PR number in the above example.
        The annotations don't influence the way `git machete` operates other than that they are displayed in the output of the `status` command.
        Also see help for the `anno` command.

        Tabs or any number of spaces can be used as indentation.
        It's only important to be consistent wrt. the sequence of characters used for indentation between all lines.
    """,
    "github": f"""
        <b>Usage: git machete github <subcommand></b>
        where <subcommand> is one of: `anno-prs`, `checkout-prs`, `create-pr`, `retarget-pr`, `sync`.

        Creates, checks out and manages GitHub PRs while keeping them reflected in branch definition file.

{textwrap.indent(github_api_access, "          ")}

{textwrap.indent(github_config_keys, "          ")}


        <b>`anno-prs`:</b>

          Annotates the branches based on their corresponding GitHub PR numbers and authors.
          Any existing annotations are overwritten for the branches that have an opened PR; annotations for the other branches remain untouched.
          Equivalent to `git machete anno --sync-github-prs`.

        <b>`checkout-prs [--all | --by=<github-login> | --mine | <PR-number-1> ... <PR-number-N>]`:</b>

          Check out the head branch of the given pull requests (specified by numbers or by a flag),
          also traverse chain of pull requests upwards, adding branches one by one to git-machete and check them out locally.
          Once the specified pull requests are checked out locally, annotate local branches with corresponding pull request numbers.
          If only one PR has been checked out, then switch the local repository's HEAD to its head branch.

          <b>Options:</b>
            <b>--all</b>     Checkout all open PRs.
            <b>--by</b>      Checkout open PRs authored by the given GitHub user.
              <b>Parameters:</b>
                <b><github-login></b> GitHub account name.
            <b>--mine</b>    Checkout open PRs for the current user associated with the GitHub token.

          <b>Parameters:</b>
            <b><PR-number-1> ... <PR-number-N></b>    Pull request numbers to checkout.

        <b>`create-pr [--draft]`:</b>

          Creates a PR for the current branch, using the upstream (parent) branch as the PR base.
          Once the PR is successfully created, annotates the current branch with the new PR's number.

          If `.git/info/description` file is present, its contents is used as PR description.
          If `.git/info/milestone` file is present, its contents (a single number - milestone id) is used as milestone.
          If `.git/info/reviewers` file is present, its contents (one GitHub login per line) are used to set reviewers.

          <b>Options:</b>
            <b>--draft</b>    Creates the new PR as a draft.

        <b>`retarget-pr`:</b>

          Sets the base of the current branch's PR to upstream (parent) branch, as seen by git machete (see `git machete show up`).

        <b>`sync`:</b>

            Synchronizes with the remote repository:
                1. checks out open PRs for the current user associated with the GitHub token and also traverses the chain of pull requests upwards, adding branches one by one to git-machete and checks them out locally as well,
                2. deletes unmanaged branches,
                3. deletes untracked managed branches that have no downstream branch.
          Equivalent of `git machete clean --checkout-my-github-prs`.
    """,
    "go": """
        <b>Usage: git machete g[o] <direction></b>
        where <direction> is one of: `d[own]`, `f[irst]`, `l[ast]`, `n[ext]`, `p[rev]`, `r[oot]`, `u[p]`

        Checks out the branch specified by the given direction relative to the current branch:
        * `down`:    the direct children/downstream branch of the current branch.
        * `first`:   the first downstream of the root branch of the current branch (like `root` followed by `next`), or the root branch itself if the root has no downstream branches.
        * `last`:    the last branch in the definition file that has the same root as the current branch; can be the root branch itself if the root has no downstream branches.
        * `next`:    the direct successor of the current branch in the definition file.
        * `prev`:    the direct predecessor of the current branch in the definition file.
        * `root`:    the root of the tree where the current branch is located. Note: this will typically be something like `develop` or `master`, since all branches are usually meant to be ultimately merged to one of those.
        * `up`:      the direct parent/upstream branch of the current branch.

        Roughly equivalent to `git checkout $(git machete show <direction>)`.
    """,
    "help": """
        <b>Usage: git machete help [<command>]</b>

        Prints a summary of this tool, or a detailed info on a command if provided.
    """,
    "hooks": """
        As with the standard git hooks, git-machete looks for its own specific hooks in `$GIT_DIR/hooks/*` (or `$(git config core.hooksPath)/*`, if set).
        All hooks are executed from the top-level folder of the repository (or top-level folder of worktree/submodule, if applicable).

        Note: `hooks` is not a command as such, just a help topic (there is no `git machete hooks` command).

        * <b>machete-post-slide-out <new-upstream> <lowest-slid-out-branch> [<new-downstreams>...]</b>
            The hook that is executed after a branch (or possibly multiple branches, in case of `slide-out`)
            is slid out by `advance`, `slide-out` or `traverse`.

            At least two parameters (branch names) are passed to the hook:
            * <b><new-upstream></b> is the upstream of the branch that has been slid out,
              or in case of multiple branches being slid out - the upstream of the highest slid out branch;
            * <b><lowest-slid-out-branch></b> is the branch that has been slid out,
              or in case of multiple branches being slid out - the lowest slid out branch;
            * <b><new-downstreams></b> are all the following (possibly zero) parameters,
              which correspond to all original downstreams of <lowest-slid-out-branch>, now reattached as the downstreams of <new-upstream>.
              Note that this may be zero, one, or multiple branches.

            Note: the hook, if present, is executed:
            * zero or once during a `advance` execution (depending on whether the slide-out has been confirmed or not),
            * exactly once during a `slide-out` execution (even if multiple branches are slid out),
            * zero or more times during `traverse` (every time a slide-out operation is confirmed).

            If the hook returns a non-zero exit code, then an error is raised and the execution of the command is aborted,
            i.e. `slide-out` won't attempt rebase of the new downstream branches and `traverse` won't continue the traversal.
            In case of `advance` there is no difference (other than exit code of the entire `advance` command being non-zero),
            since slide-out is the last operation that happens within `advance`.
            Note that non-zero exit code of the hook doesn't cancel the effects of slide-out itself, only the subsequent operations.
            The hook is executed only once the slide-out is complete and can in fact rely on .git/machete file being updated to the new branch layout.

        * <b>machete-pre-rebase <new-base> <fork-point-hash> <branch-being-rebased></b>
            The hook that is executed before rebase is run during `reapply`, `slide-out`, `traverse` and `update`.
            Note that it is NOT executed by `squash` (despite its similarity to `reapply`), since no rebase is involved in `squash`.

            The parameters are exactly the three revisions that are passed to `git rebase --onto`:
            1. what is going to be the new base for the rebased commits,
            2. what is the fork point - the place where the rebased history diverges from the upstream history,
            3. what branch is rebased.
            If the hook returns a non-zero exit code, an error is raised and the entire rebase is aborted.

            Note: this hook is independent from git's standard `pre-rebase` hook.
            If machete-pre-rebase returns zero, the execution flow continues to `git rebase`, which may also run `pre-rebase` hook if present.
            `machete-pre-rebase` is thus always launched before `pre-rebase`.

        * <b>machete-status-branch <branch-name></b>
            The hook that is executed for each branch displayed during `discover`, `status` and `traverse`.

            The standard output of this hook is displayed at the end of the line, after branch name, (optionally) custom annotation and (optionally) remote sync-ness status.
            Standard error is ignored. If the hook returns a non-zero exit code, both stdout and stderr are ignored, and printing the status continues as usual.

            Note: the hook is always invoked with `ASCII_ONLY` variable passed into the environment.
            If `status` runs in ASCII-only mode (i.e. if `--color=auto` and stdout is not a terminal, or if `--color=never`), then `ASCII_ONLY=true`, otherwise `ASCII_ONLY=false`.

        Please see hook_samples/ directory of git-machete project for examples.
        An example of using the standard git `post-commit` hook to `git machete add` branches automatically is also included.
    """,
    "is-managed": """
        <b>Usage: git machete is-managed [<branch>]</b>

        Returns with zero exit code if the given branch (or current branch, if none specified) is managed by git-machete (i.e. listed in .git/machete).

        Returns with a non-zero exit code in case:
        * the <branch> is provided but isn't managed (or doesn't exist), or
        * the <branch> isn't provided and the current branch isn't managed, or
        * the <branch> isn't provided and there's no current branch (detached HEAD).
    """,
    "list": """
        <b>Usage: git machete list <category></b>
        where <category> is one of: `addable`, `managed`, `slidable`, `slidable-after <branch>`, `unmanaged`, `with-overridden-fork-point`.

        Lists all branches that fall into one of the specified categories:
        * `addable`: all branches (local or remote) than can be added to the definition file,
        * `managed`: all branches that appear in the definition file,
        * `slidable`: all managed branches that have an upstream and can be slid out with `slide-out` command
        * `slidable-after <branch>`: the downstream branch of the <branch>, if it exists and is the only downstream of <branch> (i.e. the one that can be slid out immediately following <branch>),
        * `unmanaged`: all local branches that don't appear in the definition file,
        * `with-overridden-fork-point`: all local branches that have a fork point override set up (even if this override does not affect the location of their fork point anymore).

        This command is generally not meant for a day-to-day use, it's mostly needed for the sake of branch name completion in shell.
    """,
    "log": """
        <b>Usage: git machete l[og] [<branch>]</b>

        Runs `git log` for the range of commits from tip of the given branch (or current branch, if none specified) back to its fork point.
        See `git machete help fork-point` for more details on meaning of the "fork point".

        Note: the branch in question does not need to occur in the definition file.
    """,
    "reapply": """
        <b>Usage: git machete reapply [-f|--fork-point=<fork-point-commit>]</b>

        Interactively rebase the current branch on the top of its computed fork point.
        The chunk of the history to be rebased starts at the automatically computed fork point of the current branch by default, but can also be set explicitly by `--fork-point`.
        See `git machete help fork-point` for more details on meaning of the "fork point".

        Note: the current reapplied branch does not need to occur in the definition file.

        Tip: `reapply` can be used for squashing the commits on the current branch to make history more condensed before push to the remote,
        but there is also dedicated `squash` command that achieves the same goal without running `git rebase`.

        <b>Options:</b>
          <b>-f, --fork-point=<fork-point-commit></b>    Specifies the alternative fork point commit after which the rebased part of history is meant to start.

        <b>Environment variables:</b>
          <b>GIT_MACHETE_REBASE_OPTS</b>                 Extra options to pass to the underlying `git rebase` invocation, space-separated.
                                                  Example: `GIT_MACHETE_REBASE_OPTS="--keep-empty --rebase-merges" git machete reapply`.
    """,
    "show": """
        <b>Usage: git machete show <direction> [<branch>]</b>
        where <direction> is one of: `c[urrent]`, `d[own]`, `f[irst]`, `l[ast]`, `n[ext]`, `p[rev]`, `r[oot]`, `u[p]`
        displayed relative to given <branch>, or the current checked out branch if <branch> is unspecified.

        Outputs name of the branch (or possibly multiple branches, in case of `down`) that is:

        * `current`: the current branch; exits with a non-zero status if none (detached HEAD)
        * `down`:    the direct children/downstream branch of the given branch.
        * `first`:   the first downstream of the root branch of the given branch (like `root` followed by `next`), or the root branch itself if the root has no downstream branches.
        * `last`:    the last branch in the definition file that has the same root as the given branch; can be the root branch itself if the root has no downstream branches.
        * `next`:    the direct successor of the given branch in the definition file.
        * `prev`:    the direct predecessor of the given branch in the definition file.
        * `root`:    the root of the tree where the given branch is located. Note: this will typically be something like `develop` or `master`, since all branches are usually meant to be ultimately merged to one of those.
        * `up`:      the direct parent/upstream branch of the given branch.
    """,
    "slide-out": """
        <b>Usage: git machete slide-out [-d|--down-fork-point=<down-fork-point-commit>] [--delete] [-M|--merge] [-n|--no-edit-merge|--no-interactive-rebase] [<branch> [<branch> [<branch> ...]]]</b>

        Removes the given branch (or multiple branches) from the branch tree definition. If no branch has been specified current branch is assumed as the only branch.
        Then synchronizes the downstream (child) branches of the last specified branch on the top of the upstream (parent) branch of the first specified branch.
        Sync is performed either by rebase (default) or by merge (if `--merge` option passed).

        The most common use is to slide out a single branch whose upstream was a `develop`/`master` branch and that has been recently merged.

        Since this tool is designed to perform only one single rebase/merge at the end, provided branches must form a chain, i.e. all of the following conditions must be met:
        * for i=1..N-1, (i+1)-th branch must be the only downstream (child) branch of the i-th branch,
        * all provided branches must have an upstream branch (so, in other words, roots of branch dependency tree cannot be slid out).

        For example, let's assume the following dependency tree:
        <dim>
          develop
              adjust-reads-prec
                  block-cancel-order
                      change-table
                          drop-location-type
                      add-notification
        </dim>
        And now let's assume that `adjust-reads-prec` and later `block-cancel-order` were merged to develop.
        After running `git machete slide-out adjust-reads-prec block-cancel-order` the tree will be reduced to:
        <dim>
          develop
              change-table
                  drop-location-type
              add-notification
        </dim>
        and `change-table` and `add-notification` will be rebased onto develop (fork point for this rebase is configurable, see `-d` option below).

        Note: This command doesn't delete any branches from git, just removes them from the tree of branch dependencies.

        <b>Options:</b>
          <b>-d, --down-fork-point=<down-fork-point-commit></b>    If updating by rebase, specifies the alternative fork point for downstream branches for the operation.
                                                            `git machete fork-point` overrides for downstream branches are recommended over use of this option.
                                                            See also doc for `--fork-point` option in `git machete help reapply` and `git machete help update`.
                                                            Not allowed if updating by merge.

          <b>--delete</b>                                          Delete slid-out branches from git.

          <b>-M, --merge</b>                                       Update the downstream branch by merge rather than by rebase.

          <b>-n</b>                                                If updating by rebase, equivalent to `--no-interactive-rebase`. If updating by merge, equivalent to `--no-edit-merge`.

          <b>--no-edit-merge</b>                                   If updating by merge, skip opening the editor for merge commit message while doing `git merge` (i.e. pass `--no-edit` flag to underlying `git merge`).
                                                            Not allowed if updating by rebase.

          <b>--no-interactive-rebase</b>                           If updating by rebase, run `git rebase` in non-interactive mode (without `-i/--interactive` flag).
                                                            Not allowed if updating by merge.

        <b>Environment variables:</b>
          <b>GIT_MACHETE_REBASE_OPTS</b>                           Extra options to pass to the underlying `git rebase` invocations, space-separated.
                                                            Example: `GIT_MACHETE_REBASE_OPTS="--keep-empty --rebase-merges" git machete slide-out`.
    """,
    "squash": """
        <b>Usage: git machete squash [-f|--fork-point=<fork-point-commit>]</b>

        Squashes the commits belonging uniquely to the current branch into a single commit.
        The chunk of the history to be squashed starts at the automatically computed fork point of the current branch by default, but can also be set explicitly by `--fork-point`.
        See `git machete help fork-point` for more details on meaning of the "fork point".
        The message for the squashed is taken from the earliest squashed commit, i.e. the commit directly following the fork point.

        Note: the current squashed branch does not need to occur in the definition file.

        Tip: `squash` does NOT run `git rebase` under the hood. For more complex scenarios that require rewriting the history of current branch, see `reapply` and `update`.

        <b>Options:</b>
          <b>-f, --fork-point=<fork-point-commit></b>    Specifies the alternative fork point commit after which the squashed part of history is meant to start.
    """,
    "status": f"""
        <b>Usage: git machete s[tatus] [--color=WHEN] [-l|--list-commits] [-L|--list-commits-with-hashes] [--no-detect-squash-merges]</b>

        Displays a tree-shaped status of the branches listed in the definition file.

        Apart from simply ASCII-formatting the definition file, this also:

        * colors the edges between upstream (parent) and downstream (children) branches:

          - <b><red>red edge</red></b> means that the downstream branch tip is <b>not a direct descendant</b> of the upstream branch tip,

          - <b><yellow>yellow edge</yellow></b> means that the downstream branch tip is a <b>direct descendant</b> of the upstream branch tip,
            but the fork point (see help on `fork-point`) of the downstream branch is <b>not equal</b> to the upstream branch tip,

          - <b><green>green edge</green></b> means that the downstream branch tip is a <b>direct descendant</b> of the upstream branch tip
            and the fork point of the downstream branch is <b>equal</b> to the upstream branch tip,

          - <b><dim>grey/dimmed edge</dim></b> means that the downstream branch has been <b>merged</b> to the upstream branch,
            detected by commit equivalency (default), or by strict detection of merge commits (if `--no-detect-squash-merges` passed).


        * prints `(untracked/ahead of <remote>/behind <remote>/diverged from [& older than] <remote>)` message if the branch is not in sync with its remote counterpart;

        * displays the custom annotations (see help on `format` and `anno`) next to each branch, if present;

        * displays the output of `machete-status-branch` hook (see help on `hooks`), if present;

        * optionally lists commits introduced on each branch if `-l`/`--list-commits` or `-L`/`--list-commits-with-hashes` is supplied.

        Name of the currently checked-out branch is underlined (or shown in blue on terminals that don't support underline).

        In case of yellow edge, use `-l` flag to show the exact location of the inferred fork point
        (which indicates e.g. what range of commits is going to be rebased when the branch is updated).
        The inferred fork point can be always overridden manually, see help on `fork-point`.

        Grey/dimmed edge suggests that the downstream branch can be slid out (see help on `slide-out` and `traverse`).

        Using colors can be disabled with a `--color` flag set to `never`.
        With `--color=always`, git machete always emits colors and with `--color=auto`, it emits colors only when standard output is connected to a terminal.
        `--color=auto` is the default. When colors are disabled, relation between branches is represented in the following way (not including the hash-comments):
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
        <b>Options:</b>
          <b>--color=WHEN</b>                      Colorize the output; WHEN can be `always`, `auto` (default; i.e. only if stdout is a terminal), or `never`.

          <b>-l, --list-commits</b>                Additionally list the commits introduced on each branch.

          <b>-L, --list-commits-with-hashes</b>    Additionally list the short hashes and messages of commits introduced on each branch.

          <b>--no-detect-squash-merges</b>         Only consider "strict" (fast-forward or 2-parent) merges, rather than rebase/squash merges,
                                            when detecting if a branch is merged into its upstream (parent).

        <b>Config keys:</b>
{textwrap.indent(status_extraSpaceBeforeBranchName_config_key, "          ")}
    """,
    "traverse": """
        <b>Usage: git machete t[raverse] [-F|--fetch] [-l|--list-commits] [-M|--merge]
                                         [-n|--no-edit-merge|--no-interactive-rebase] [--no-detect-squash-merges]
                                         [--[no-]push] [--[no-]push-untracked]
                                         [--return-to=WHERE] [--start-from=WHERE] [-w|--whole] [-W] [-y|--yes]</b>

        Traverses the branch tree in pre-order (i.e. simply in the order as they occur in the definition file).
        By default `traverse` starts from the current branch.
        This behaviour can, however, be customized using options: `--start-from=`, `--whole` or `-w`, `-W`.

        For each branch, the command:
        * detects if the branch is merged (<b><dim>grey</dim></b> edge) to its parent (aka upstream)
          - by commit equivalency (default), or by strict detection of merge commits (if `--no-detect-squash-merges` passed),
          - if so, asks the user whether to slide out the branch from the dependency tree (typically branches are no longer needed after they're merged);
        * otherwise, if the branch has a <b><red>red</red></b> or <b><yellow>yellow</yellow></b> edge to its parent/upstream (see `status`):
          - asks the user whether to rebase (default) or merge (if `--merge` passed) the branch onto into its upstream branch - equivalent to `git machete update` with no `--fork-point` option passed;

        * if the branch is not tracked on a remote, is ahead of its remote counterpart, or diverged from the counterpart & has newer head commit than the counterpart:
          - asks the user whether to push the branch (possibly with `--force-with-lease` if the branches diverged);
        * otherwise, if the branch diverged from the remote counterpart & has older head commit than the counterpart:
          - asks the user whether to `git reset --keep` the branch to its remote counterpart
        * otherwise, if the branch is behind its remote counterpart:
          - asks the user whether to pull the branch;

        * and finally, if any of the above operations has been successfully completed:
          - prints the updated `status`.

        If the traverse flow is stopped (typically due to merge/rebase conflicts), just run `git machete traverse` after the merge/rebase is finished.
        It will pick up the walk from the current branch (unless `--start-from=` or `-w` etc. is passed).
        Unlike with e.g. `git rebase`, there is no special `--continue` flag, as `traverse` is stateless
        (doesn't keep a state of its own like `git rebase` does in `.git/rebase-apply/`).

        <b>Options:</b>
          <b>-F, --fetch</b>                  Fetch the remotes of all managed branches at the beginning of traversal (no `git pull` involved, only `git fetch`).

          <b>-l, --list-commits</b>           When printing the status, additionally list the messages of commits introduced on each branch.

          <b>-M, --merge</b>                  Update by merge rather than by rebase.

          <b>-n</b>                           If updating by rebase, equivalent to `--no-interactive-rebase`. If updating by merge, equivalent to `--no-edit-merge`.

          <b>--no-detect-squash-merges</b>    Only consider "strict" (fast-forward or 2-parent) merges, rather than rebase/squash merges,
                                       when detecting if a branch is merged into its upstream (parent).

          <b>--no-edit-merge</b>              If updating by merge, skip opening the editor for merge commit message while doing `git merge` (i.e. pass `--no-edit` flag to underlying `git merge`).
                                       Not allowed if updating by rebase.

          <b>--no-interactive-rebase</b>      If updating by rebase, run `git rebase` in non-interactive mode (without `-i/--interactive` flag).
                                       Not allowed if updating by merge.

          <b>--no-push</b>                    Do not push any (neither tracked nor untracked) branches to remote, re-enable via `--push`.

          <b>--no-push-untracked</b>          Do not push untracked branches to remote, re-enable via `--push-untracked`.

          <b>--push</b>                       Push all (both tracked and untracked) branches to remote - default behavior.

          <b>--push-untracked</b>             Push untracked branches to remote - default behavior.

          <b>--return-to=WHERE</b>            Specifies the branch to return after traversal is successfully completed; WHERE can be `here` (the current branch at the moment when traversal starts),
                                       `nearest-remaining` (nearest remaining branch in case the `here` branch has been slid out by the traversal)
                                       or `stay` (the default - just stay wherever the traversal stops).
                                       Note: when user quits by `q/yq` or when traversal is stopped because one of git actions fails, the behavior is always `stay`.

          <b>--start-from=WHERE</b>           Specifies the branch to start the traversal from; WHERE can be `here` (the default - current branch, must be managed by git-machete),
                                       `root` (root branch of the current branch, as in `git machete show root`) or `first-root` (first listed managed branch).

          <b>-w, --whole</b>                  Equivalent to `-n --start-from=first-root --return-to=nearest-remaining`;
                                       useful for quickly traversing & syncing all branches (rather than doing more fine-grained operations on the local section of the branch tree).

          <b>-W</b>                           Equivalent to `--fetch --whole`; useful for even more automated traversal of all branches.

          <b>-y, --yes</b>                    Don't ask for any interactive input, including confirmation of rebase/push/pull. Implies `-n`.

        <b>Environment variables:</b>
          <b>GIT_MACHETE_REBASE_OPTS</b>      Extra options to pass to the underlying `git rebase` invocations, space-separated.
                                       Example: `GIT_MACHETE_REBASE_OPTS="--keep-empty --rebase-merges" git machete traverse`.
    """,
    "update": """
        <b>Usage: git machete update [-f|--fork-point=<fork-point-commit>] [-M|--merge] [-n|--no-edit-merge|--no-interactive-rebase]</b>

        Synchronizes the current branch with its upstream (parent) branch either by rebase (default) or by merge (if `--merge` option passed).

        If updating by rebase, interactively rebases the current branch on the top of its upstream (parent) branch.
        The chunk of the history to be rebased starts at the fork point of the current branch, which by default is inferred automatically, but can also be set explicitly by `--fork-point`.
        See `git machete help fork-point` for more details on meaning of the "fork point".

        If updating by merge, merges the upstream (parent) branch into the current branch.

        <b>Options:</b>
          <b>-f, --fork-point=<fork-point-commit></b>    If updating by rebase, specifies the alternative fork point commit after which the rebased part of history is meant to start.
                                                  Not allowed if updating by merge.

          <b>-M, --merge</b>                             Update by merge rather than by rebase.

          <b>-n</b>                                      If updating by rebase, equivalent to `--no-interactive-rebase`. If updating by merge, equivalent to `--no-edit-merge`.

          <b>--no-edit-merge</b>                         If updating by merge, skip opening the editor for merge commit message while doing `git merge` (i.e. pass `--no-edit` flag to underlying `git merge`).
                                                  Not allowed if updating by rebase.

          <b>--no-interactive-rebase</b>                 If updating by rebase, run `git rebase` in non-interactive mode (without `-i/--interactive` flag).
                                                  Not allowed if updating by merge.

        <b>Environment variables:</b>
          <b>GIT_MACHETE_REBASE_OPTS</b>                 Extra options to pass to the underlying `git rebase` invocation, space-separated.
                                                  Example: `GIT_MACHETE_REBASE_OPTS="--keep-empty --rebase-merges" git machete update`.
    """,
    "version": """
        <b>Usage: git machete version</b>

        Prints the version and exits.
    """
}
