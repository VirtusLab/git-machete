#compdef git-machete

_git-machete() {
  local common_flags=(
    '(--debug)'--debug'[Log detailed diagnostic info, including outputs of the executed git commands]'
    '(-h --help)'{-h,--help}'[Print help and exit]'
    '(-v --verbose)'{-v,--verbose}'[Log the executed git commands]'
  )

  _arguments -C \
    '1: :__git_machete_commands' \
    '*::arg:->args' \
    "${common_flags[@]}" \
    '(--version)'--version'[Print version and exit]'

  case $state in
    (args)
      case ${line[1]} in
        (add)
          _arguments \
            '1:: :__git_machete_list_addable' \
            '(-R --as-root -f --as-first-child)'{-f,--as-first-child}'[Add the given branch as the first (instead of last) child of its parent]' \
            '(-R --as-root -f --as-first-child -o --onto)'{-R,--as-root}'[Add the given branch as a new root]' \
            '(-R --as-root -o --onto)'{-o,--onto=}'[Specify the target parent branch to add the given branch onto]: :__git_machete_list_managed' \
            '(-y --yes)'{-y,--yes}'[Do not ask for confirmation whether to create the branch or whether to add onto the inferred upstream]' \
            "${common_flags[@]}"
          ;;
        (advance)
          _arguments \
            '(-y --yes)'{-y,--yes}'[Do not ask for confirmation]' \
            "${common_flags[@]}"
          ;;
        (anno)
          _arguments \
            '(-b --branch)'{-b,--branch=}'[Branch to set the annotation for]: :__git_machete_list_managed' \
            '(-L --sync-gitlab-mrs -H --sync-github-prs)'{-H,--sync-github-prs}'[Annotate with GitHub PR numbers and author logins where applicable]' \
            '(-H --sync-github-prs -L --sync-gitlab-mrs)'{-L,--sync-gitlab-mrs}'[Annotate with GitLab MR numbers and author logins where applicable]' \
            "${common_flags[@]}"
          ;;
        (completion)
          _arguments \
            '1:: :__git_machete_completion_shells' \
            "${common_flags[@]}"
          ;;
        (delete-unmanaged)
          _arguments \
            '(-y --yes)'{-y,--yes}'[Do not ask for confirmation when deleting unmanaged branches]' \
            "${common_flags[@]}"
          ;;
        (d|diff)
          _arguments \
            '1:: :__git_branch_names' \
            '(-s --stat)'{-s,--stat}'[Pass --stat option to git diff, so that only summary (diffstat) is printed]' \
            "${common_flags[@]}"
          ;;
        (discover)
          # TODO (#111): complete the comma-separated list of roots
          _arguments \
            '(-C --checked-out-since)'{-C,--checked-out-since=}'[Only consider branches checked out at least once since the given date]' \
            '(-l --list-commits)'{-l,--list-commits}'[List the messages of commits introduced on each branch]' \
            '(-r --roots)'{-r,--roots=}'[Comma-separated list of branches to be considered roots of trees of branch dependencies (typically develop and/or master)]: :__git_branch_names' \
            '(-y --yes)'{-y,--yes}'[Do not ask for confirmation]' \
            "${common_flags[@]}"
          ;;
        (e|edit|file)
          _arguments "${common_flags[@]}"
          ;;
        (fork-point)
          _arguments '1:: :__git_branch_names' \
            '(--inferred --override-to --override-to-inferred --override-to-parent --unset-override)'--inferred'[Display the fork point ignoring any potential override]' \
            '(--inferred --override-to --override-to-inferred --override-to-parent --unset-override)'--override-to='[Override fork point to the given revision]: :__git_references' \
            '(--inferred --override-to --override-to-inferred --override-to-parent --unset-override)'--override-to-inferred'[Override fork point to the inferred location]' \
            '(--inferred --override-to --override-to-inferred --override-to-parent --unset-override)'--override-to-parent'[Override fork point to the upstream (parent) branch]' \
            '(--inferred --override-to --override-to-inferred --override-to-parent --unset-override)'--unset-override='[Unset fork point override by removing machete.overrideForkPoint.<branch>.* configs]: :__git_machete_list_with_overridden_fork_point' \
            "${common_flags[@]}"
          ;;
        (g|go)
          _arguments \
            '1:: :__git_machete_directions_go' \
            "${common_flags[@]}"
          ;;
        (github)
          __git_machete_github_subcommands
          ;;
        (gitlab)
          __git_machete_gitlab_subcommands
          ;;
        (help)
          _arguments \
            '1:: :__git_machete_help_topics' \
            "${common_flags[@]}"
          ;;
        (is-managed|l|log)
          _arguments \
            '1:: :__git_branch_names' \
            "${common_flags[@]}"
          ;;
        (list)
          _arguments \
            '1:: :__git_machete_categories' \
            "${common_flags[@]}"
          ;;
        (reapply)
          _arguments \
            '(-f --fork-point)'{-f,--fork-point=}'[Fork point commit after which the rebased part of history is meant to start]: :__git_references' \
            "${common_flags[@]}"
          ;;
        (show)
          _arguments \
            '1:: :__git_machete_directions_show' \
            '2:: :__git_machete_list_managed' \
            "${common_flags[@]}"
          ;;
        (slide-out)
          # TODO (#113): suggest further branches based on the previous specified branch (like in Bash completion script)
          _arguments \
            '*:: :__git_machete_list_slidable' \
            '(--removed-from-remote -M --merge --no-rebase -d --down-fork-point)'{-d,--down-fork-point=}'[If updating by rebase, specify fork point commit after which the rebased part of history of the downstream branch is meant to start]: :__git_references' \
            '(--delete)'--delete'[Delete branches after sliding them out]' \
            '(--removed-from-remote -d --down-fork-point --no-interactive-rebase --no-rebase -M --merge)'{-M,--merge}'[Update by merge rather than by rebase]' \
            '(--removed-from-remote -n --no-edit-merge --no-interactive-rebase)'-n'[If updating by rebase, equivalent to --no-interactive-rebase. If updating by merge, equivalent to --no-edit-merge]' \
            '(--removed-from-remote -n --no-edit-merge --no-interactive-rebase --no-rebase)'--no-edit-merge'[If updating by merge, pass --no-edit flag to underlying git merge]' \
            '(--removed-from-remote -M --merge -n --no-edit-merge --no-interactive-rebase --no-rebase)'--no-interactive-rebase'[If updating by rebase, do NOT pass --interactive flag to underlying git rebase]' \
            '(--removed-from-remote -d --down-fork-point -M --merge --no-interactive-rebase --no-edit-merge --no-rebase)'--no-rebase'[Skip rebase of downstream branches after sliding out]' \
            '(--removed-from-remote -d --down-fork-point -M --merge -n --no-edit-merge --no-interactive-rebase --no-rebase)'--removed-from-remote'[Slide out all branches removed from the remote]' \
            "${common_flags[@]}"
          ;;
        (squash)
          _arguments \
            '(-f --fork-point)'{-f,--fork-point=}'[Fork point commit after which the squashed part of history is meant to start]: :__git_references' \
            "${common_flags[@]}"
          ;;
        (s|status)
          _arguments \
            '(--color)'--color='[Colorize the output; argument can be "always", "auto", or "never"]: :__git_machete_opt_color_args' \
            '(-L --list-commits-with-hashes)'{-L,--list-commits-with-hashes}'[List the short hashes and messages of commits introduced on each branch]' \
            '(-l --list-commits)'{-l,--list-commits}'[List the messages of commits introduced on each branch]' \
            '(--no-detect-squash-merges)'--no-detect-squash-merges'[Only consider "strict" (fast-forward or 2-parent) merges, rather than rebase/squash merges, when detecting if a branch is merged into its upstream]' \
            "${common_flags[@]}"
          ;;
        (t|traverse)
          _arguments \
            '(-W -F --fetch)'{-F,--fetch}'[Fetch the remotes of all managed branches at the beginning of traversal]' \
            '(-L --sync-gitlab-mrs -H --sync-github-prs)'{-H,--sync-github-prs}'[Create and retarget GitHub PRs while traversing]' \
            '(-H --sync-github-prs -L --sync-gitlab-mrs)'{-L,--sync-gitlab-mrs}'[Create and retarget GitLab MRs while traversing]' \
            '(-W -l --list-commits)'{-l,--list-commits}'[List the messages of commits introduced on each branch]' \
            '(--no-interactive-rebase -M --merge)'{-M,--merge}'[Update by merge rather than by rebase]' \
            '(-n --no-edit-merge --no-interactive-rebase -y --yes)'-n'[If updating by rebase, equivalent to --no-interactive-rebase. If updating by merge, equivalent to --no-edit-merge]' \
            '(--no-detect-squash-merges)'--no-detect-squash-merges'[Only consider "strict" (fast-forward or 2-parent) merges, rather than rebase/squash merges, when detecting if a branch is merged into its upstream]' \
            '(-n --no-edit-merge)'--no-edit-merge'[If updating by merge, pass --no-edit flag to underlying git merge]' \
            '(-n -M --merge --no-interactive-rebase)'--no-interactive-rebase'[If updating by rebase, do NOT pass --interactive flag to underlying git rebase]' \
            '(--push --no-push)'--no-push'[Do not push any (neither tracked nor untracked) branches to remote]' \
            '(--push-untracked --no-push-untracked)'--no-push-untracked'[Do not push untracked branches to remote]' \
            '(--no-push --push)'--push'[Push all (both tracked and untracked) branches to remote (default behavior)]' \
            '(--no-push-untracked --push-untracked)'--push-untracked'[Push untracked branches to remote (default behavior)]' \
            '(--return-to)'--return-to='[The branch to return after traversal is successfully completed; argument can be "here", "nearest-remaining", or "stay"]: :__git_machete_opt_return_to_args' \
            '(--start-from)'--start-from='[The branch to start the traversal from; argument can be "here", "root", "first-root", or any branch name]: :__git_machete_opt_start_from_args_or_branches' \
            '(--stop-after)'--stop-after='[The branch to stop the traversal after]: :__git_branch_names' \
            '(-W -w --whole)'{-w,--whole}'[Equivalent to -n --start-from=first-root --return-to=nearest-remaining]' \
            '(-F --fetch -l --list-commits -w --whole -W)'-W'[Equivalent to --fetch --whole]' \
            '(-n -y --yes)'{-y,--yes}'[Do not ask for any interactive input; implicates -n]' \
            "${common_flags[@]}"
          ;;
         (update)
          _arguments \
            '(-M --merge -f --fork-point)'{-f,--fork-point=}'[If updating by rebase, specify fork point commit after which the rebased part of history is meant to start]: :__git_references' \
            '(-f --fork-point --no-interactive-rebase -M --merge)'{-M,--merge}'[Update by merge rather than by rebase]' \
            '(-n --no-edit-merge --no-interactive-rebase)'-n'[If updating by rebase, equivalent to --no-interactive-rebase. If updating by merge, equivalent to --no-edit-merge]' \
            '(-n --no-edit-merge)'--no-edit-merge'[If updating by merge, pass --no-edit flag to underlying git merge]' \
            '(-n -M --merge --no-interactive-rebase)'--no-interactive-rebase'[If updating by rebase, do NOT pass --interactive flag to underlying git rebase]' \
            "${common_flags[@]}"
          ;;
      esac
  esac
}

__git_machete_cmds=(
  'add:Add a branch to the tree of branch dependencies'
  'advance:Fast-forward the current branch to match one of its downstreams and subsequently slide out this downstream'
  'anno:Manage custom annotations'
  'completion:Print completion script for the given shell'
  'delete-unmanaged:Delete local branches that are not present in the branch layout file'
  'diff:Diff current working directory or a given branch against its fork point'
  'discover:Automatically discover tree of branch dependencies'
  'edit:Edit the branch layout file'
  'file:Display the location of the branch layout file'
  'fork-point:Display hash of the fork point commit of a branch'
  'github:Creates, checks out and manages GitHub PRs while keeping them reflected in branch layout file'
  'gitlab:Creates, checks out and manages GitLab MRs while keeping them reflected in branch layout file'
  'go:Check out the branch relative to the position of the current branch'
  'help:Display this overview, or detailed help for a specified command'
  'is-managed:Check if the current branch is managed by git-machete (mostly for scripts)'
  'list:List all branches that fall into one of pre-defined categories (mostly for internal use)'
  'log:Log the part of history specific to the given branch'
  'reapply:Rebase the current branch onto its own fork point'
  'show:Show name(s) of the branch(es) relative to the position of the current branch'
  'slide-out:Slide the current branch out and sync its downstream (child) branch with its upstream (parent) branch via rebase or merge'
  'squash:Squash the unique history of the current branch into a single commit'
  'status:Display formatted tree of branch dependencies, including info on their sync with upstream branch and with remote'
  'traverse:Walk through the tree of branch dependencies and rebase, merge, slide out, push and/or pull each branch one by one'
  'update:Sync the current branch with its upstream (parent) branch via rebase or merge'
  'version:Display version and exit'
)

__git_machete_directions=(
  'down:child(ren) in tree of branch dependencies'
  'first:first child of the current root branch'
  'last:last branch located under current root branch'
  'next:the one defined in the following line in .git/machete file'
  'prev:the one defined in the preceding line in .git/machete file'
  'root:root of the tree of branch dependencies where current branch belongs'
  'up:parent in tree of branch dependencies'
)

__git_machete_commands() {
  _describe 'git machete command' __git_machete_cmds
}

__git_machete_help_topics() {
  local topics
  set -A topics ${__git_machete_cmds}
  topics+=(
    'config:Docs for the configuration keys and environment variables'
    'format:Format of the .git/machete branch layout file'
    'hooks:Display docs for the extra hooks added by git machete'
  )
  _describe 'git machete help topic' topics
}

__git_machete_directions_go() {
  _describe 'direction' __git_machete_directions
}

__git_machete_directions_show() {
  local directions
  directions=(
    'current'
    "${__git_machete_directions[@]}"
  )
  _describe 'direction' directions
}

__git_machete_github_subcommands() {
  local curcontext="$curcontext" state line
  typeset -A opt_args

  _arguments -C \
    ':command:->command' \
    '*::options:->options'

  case $state in
    (command)

      local -a github_subcommands
      github_subcommands=(
        'anno-prs:annotate the branches based on their corresponding GitHub PR numbers and authors'
        'checkout-prs:check out the given pull requests locally'
        'create-pr:create a PR for the current branch, using the upstream (parent) branch as the PR base'
        'restack-pr:(force-)push and retarget the PR, without adding code owners as reviewers in the process'
        'retarget-pr:set the base of the current branch PR to upstream (parent) branch'
        'update-pr-descriptions:update the generated sections of PR descriptions that lists the upstream and/or downstream PRs'
      )
      _describe 'subcommand' github_subcommands
      ;;

    (options)
      case $line[1] in

        (anno-prs) \
          _arguments \
            '(--with-urls)'--with-urls'[Include PR URLs in the annotations]' \
            "${common_flags[@]}"
        ;;

        (checkout-prs)
          _arguments \
            '(--all)'--all'[Checkout all open PRs]' \
            '(--by)'--by='[Checkout open PRs authored by the given GitHub user]' \
            '(--mine)'--mine'[Checkout open PRs for the current user associated with the GitHub token]' \
            "${common_flags[@]}"
        ;;

        (create-pr)
          _arguments \
            '(--draft)'--draft'[Create the new PR as draft]' \
            '(--title)'--title='[Set the title for new PR explicitly]' \
            '(-U --update-related-descriptions)'{-U,--update-related-descriptions}'[Update the generated sections of PR descriptions that list the upstream and/or downstream PRs]' \
            '(-y --yes)'{-y,--yes}'[Do not ask for confirmation whether to push the branch]' \
            "${common_flags[@]}"
        ;;

        (restack-pr)
          _arguments \
            '(-U --update-related-descriptions)'{-U,--update-related-descriptions}'[Update the generated sections of PR descriptions that list the upstream and/or downstream PRs]' \
            "${common_flags[@]}"
        ;;

        (retarget-pr)
          _arguments \
            '(-b --branch)'{-b,--branch=}'[Specify the branch for which the associated PR base will be set to its upstream (parent) branch]: :__git_machete_list_managed' \
            '(--ignore-if-missing)'--ignore-if-missing'[Ignore errors and quietly terminate execution if there is no PR opened for current (or specified) branch]' \
            '(-U --update-related-descriptions)'{-U,--update-related-descriptions}'[Update the generated sections of PR descriptions that list the upstream and/or downstream PRs]' \
            "${common_flags[@]}"
        ;;

        (update-pr-descriptions)
          _arguments \
            '(--all)'--all'[Update PR descriptions for all PRs in the repository]' \
            '(--by)'--by='[Update PR descriptions for all PRs authored by the given GitHub user]' \
            '(--mine)'--mine'[Update PR descriptions for all PRs opened by the current user associated with the GitHub token]' \
            '(--related)'--related'[Update PR descriptions for all PRs that are upstream and/or downstream of the PR for the current branch]' \
            "${common_flags[@]}"
        ;;
      esac
    ;;
  esac
}

__git_machete_gitlab_subcommands() {
  local curcontext="$curcontext" state line
  typeset -A opt_args

  _arguments -C \
    ':command:->command' \
    '*::options:->options'

  case $state in
    (command)

      local -a gitlab_subcommands
      gitlab_subcommands=(
        'anno-mrs:annotate the branches based on their corresponding GitLab MR numbers and authors'
        'checkout-mrs:check out the given merge requests locally'
        'create-mr:create an MR for the current branch, using the upstream (parent) branch as the MR source branch'
        'restack-mr:(force-)push and retarget the MR, without adding code owners as reviewers in the process'
        'retarget-mr:set the source branch of the current branch MR to upstream (parent) branch'
        'update-mr-descriptions:update the generated sections of MR descriptions that list the upstream and/or downstream MRs'
      )
      _describe 'subcommand' gitlab_subcommands
      ;;

    (options)
      case $line[1] in

        (anno-mrs) \
          _arguments \
            '(--with-urls)'--with-urls'[Include MR URLs in the annotations]' \
            "${common_flags[@]}"
        ;;

        (checkout-mrs)
          _arguments \
            '(--all)'--all'[Checkout all open MRs]' \
            '(--by)'--by='[Checkout open MRs authored by the given GitLab user]' \
            '(--mine)'--mine'[Checkout open MRs for the current user associated with the GitLab token]' \
            "${common_flags[@]}"
        ;;

        (create-mr)
          _arguments \
            '(--draft)'--draft'[Create the new MR as draft]' \
            '(--title)'--title='[Set the title for new MR explicitly]' \
            '(-U --update-related-descriptions)'{-U,--update-related-descriptions}'[Update the generated sections of MR descriptions that list the upstream and/or downstream MRs]' \
            '(-y --yes)'{-y,--yes}'[Do not ask for confirmation whether to push the branch]' \
            "${common_flags[@]}"
        ;;

        (restack-mr)
          _arguments \
            '(-U --update-related-descriptions)'{-U,--update-related-descriptions}'[Update the generated sections of MR descriptions that list the upstream and/or downstream MRs]' \
            "${common_flags[@]}"
        ;;

        (retarget-mr)
          _arguments \
            '(-b --branch)'{-b,--branch=}'[Specify the branch for which the associated MR source branch will be set to its upstream (parent) branch]: :__git_machete_list_managed' \
            '(--ignore-if-missing)'--ignore-if-missing'[Ignore errors and quietly terminate execution if there is no MR opened for current (or specified) branch]' \
            '(-U --update-related-descriptions)'{-U,--update-related-descriptions}'[Update the generated sections of MR descriptions that list the upstream and/or downstream MRs]' \
            "${common_flags[@]}"
        ;;

        (update-mr-descriptions)
          _arguments \
            '(--all)'--all'[Update MR descriptions for all MRs in the project]' \
            '(--by)'--by='[Update MR descriptions for all MRs authored by the given GitLab user]' \
            '(--mine)'--mine'[Update MR descriptions for all MRs opened by the current user associated with the GitLab token]' \
            '(--related)'--related'[Update MR descriptions for all MRs that are upstream and/or downstream of the MR for the current branch]' \
            "${common_flags[@]}"
        ;;
      esac
    ;;
  esac
}

__git_machete_categories() {
  local categories
  # TODO (#115): complete slidable-after's argument
  categories=(
    'addable:all branches (local or remote) than can be added to the branch layout file'
    'childless:all branches that do not possess child branches'
    'managed:all branches that appear in the branch layout file'
    'slidable:all managed branches that have exactly one upstream and one downstream (i.e. the ones that can be slid out with slide-out command)'
    'slidable-after:the downstream branch of the given branch, if it exists and is its only downstream (i.e. the one that can be slid out immediately following <branch>)'
    'unmanaged:all local branches that do not appear in the branch layout file'
    'with-overridden-fork-point:all local branches that have a fork point override config'
  )
  _describe 'category' categories
}

__git_machete_opt_color_args() {
  local opt_color_args
  opt_color_args=(
    'always:always emits colors'
    'auto:emits colors only when standard output is connected to a terminal'
    'never:colors are disabled'
  )
  _describe 'color argument' opt_color_args
}

__git_machete_opt_return_to_args() {
  local opt_return_to
  opt_return_to=(
    'HERE:the current branch at the moment when traversal starts'
    'NEAREST-REMAINING:nearest remaining branch in case the here branch has been slid out'
    'STAY:the default - just stay wherever the traversal stops'
  )
  _describe 'return-to argument' opt_return_to
}

__git_machete_opt_start_from_args() {
  local opt_start_from
  opt_start_from=(
    'HERE:the default - current branch, must be managed by git-machete'
    'ROOT:root branch of the current branch, as in git machete show root'
    'FIRST-ROOT:first listed managed branch'
  )
  _describe 'start-from argument' opt_start_from
}

__git_machete_opt_start_from_args_or_branches() {
  __git_machete_opt_start_from_args
  __git_branch_names
}
__git_machete_list_addable() {
  local result
  IFS=$'\n' result=($(git machete list addable 2>/dev/null))
  _describe 'addable branch' result
}

__git_machete_list_managed() {
  local result
  IFS=$'\n' result=($(git machete list managed 2>/dev/null))
  _describe 'managed branch' result
}

__git_machete_list_slidable() {
  local result
  IFS=$'\n' result=($(git machete list slidable 2>/dev/null))
  _describe 'slidable branch' result
}

__git_machete_list_with_overridden_fork_point() {
  local result
  IFS=$'\n' result=($(git machete list with-overridden-fork-point 2>/dev/null))
  _describe 'branch with overridden fork point' result
}

__git_machete_completion_shells() {
  local shells
  shells=(bash fish zsh)
  _describe 'shell' shells
}

zstyle ':completion:*:*:git:*' user-commands machete:'organize your repo, instantly rebase/merge/push/pull and more'
