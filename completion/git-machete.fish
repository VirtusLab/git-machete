# This file will be loaded by git.fish completions and also provide all __fish_git_* functions here.
#
# Caveat:
# > if the user types git-machete, then only git-machete.fish will be loaded, but you can trick
# > fish into still loading git.fish by adding a complete --do-complete="git " at the top
# - https://gitter.im/fish-shell/fish-shell?at=6176a4bacd4972068b6a0804
complete --do-complete="git "

set -l __mcht_help_topics format hooks
set -l __mcht_commands_long add advance anno delete-unmanaged diff discover edit file fork-point \
  github go help is-managed list log reapply show slide-out squash status traverse update version
set -l __mcht_commands_short d e g l s
set -l __mcht_commands $__mcht_commands_long $__mcht_commands_short

# git
complete -c git -n "__fish_git_needs_command" -f -a machete -d 'Tool for managing git workflows'
complete -c git -n "__fish_git_using_command machete" -f # (suppress file completion)

# git machete (general options)
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands; and not __fish_seen_subcommand_from --help -h" -f -s h -d 'Print help and exit'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from $__mcht_commands;     and not __fish_seen_subcommand_from --help -h" -f -l help -s h -d 'Print help and exit'
#     Parameters --help work for subcommands only. ---^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#     See: https://github.com/VirtusLab/git-machete/issues/25
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from --verbose -v" -f -l verbose -s v -d 'Log the executed git commands'
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from --debug"      -f -l debug        -d 'Log detailed diagnostic info, including outputs of the executed git commands'
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from --version"    -f -l version      -d 'Print version and exit'

# git machete add
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands"                                            -f                 -a add                           -d 'Add a branch to the tree of branch dependencies'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from add; and not __fish_seen_subcommand_from --as-root -R"           -x -l onto    -s o -a '(__fish_git_local_branches)' -d 'Specifies the target parent branch to add the given branch onto. Cannot be specified together with -R/--as-root'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from add; and not __fish_seen_subcommand_from --onto -o --as-root -R" -f -l as-root -s R                                  -d 'Add the given branch as a new root (and not onto any other branch). Cannot be specified together with -o/--onto'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from add; and not __fish_seen_subcommand_from --yes -y"               -f -l yes     -s y                                  -d 'Don\'t ask for confirmation whether to create the branch or whether to add onto the inferred upstream'

# git machete advance
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands"                                  -f -a advance  -d 'Fast-forward merge one of children to the current branch and then slide out this child'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from advance; and not __fish_seen_subcommand_from --yes -y" -f -l yes -s y -d 'Don\'t ask for confirmation whether to fast-forward the current branch or whether to slide-out the downstream. Fails if the current branch has more than one green-edge downstream branch'

# git machete anno
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands"                                           -f                         -a anno                          -d 'Manage custom annotations'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from anno"                                                           -x -l branch          -s b -a '(__fish_git_local_branches)' -d 'Branch to set the annotation for'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from anno; and not __fish_seen_subcommand_from --sync-github-prs -H" -f -l sync-github-prs -s H                                  -d 'Annotate with GitHub PR numbers and authors where applicable'

# git machete clean
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands"                                                     -f -a clean                          -d 'Delete untracked and unmanaged branches, and optionally check out open GitHub PRs'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from clean; and not __fish_seen_subcommand_from --checkout-my-github-prs -H"   -f -l checkout-my-github-prs -s H    -d 'Checkout open PRs for the current user associated with the GitHub token'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from clean; and not __fish_seen_subcommand_from --yes -y"                      -f -l yes -s y                       -d 'Don\'t ask for confirmation'


# git machete delete-unmanaged
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands"                                           -f -a delete-unmanaged -d 'Delete local branches that are not present in the definition file'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from delete-unmanaged; and not __fish_seen_subcommand_from --yes -y" -f -l yes -s y         -d 'Don\'t ask for confirmation'

# git machete discover
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands"                                                 -f                           -a discover                      -d 'Automatically discover tree of branch dependencies'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from discover; and not __fish_seen_subcommand_from --checked-out-since -C" -x -l checked-out-since -s C                                  -d 'Only consider branches checked out at least once since the given date. <date> can be e.g. 2 weeks ago or 2020-06-01, as in git log --since=<date>. If not present, the date is selected automatically so that around 10 branches are included'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from discover; and not __fish_seen_subcommand_from --list-commits -l"      -f -l list-commits      -s l                                  -d 'When printing the discovered tree, additionally lists the messages of commits introduced on each branch (as for git machete status)'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from discover"                                                             -x -l roots             -s r -a '(__fish_git_local_branches)' -d 'Comma-separated list of branches that should be considered roots of trees of branch dependencies. If not present, master is assumed to be a root. Note that in the process of discovery, certain other branches can also be additionally deemed to be roots as well'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from discover; and not __fish_seen_subcommand_from --yes -y"               -f -l yes               -s y                                  -d 'Don\'t ask for confirmation before saving the newly-discovered tree. Mostly useful in scripts; not recommended for manual use'

# git machete diff
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands"                                  -f -a diff      -d 'Diff current working directory or a given branch against its computed fork point'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from diff d; and not __fish_seen_subcommand_from --stat -s" -f -l stat -s s -d 'Makes git machete diff pass --stat option to git diff, so that only summary (diffstat) is printed'

# git machete edit
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands" -f -a edit -d 'Edit the definition file'

# git machete file
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands" -f -a file -d 'Display the location of the definition file'

# git machete fork-point
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands" -f -a fork-point -d 'Display or override fork point for a branch'
# all forms
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from fork-point" -f -a '(__fish_git_local_branches)'
# form 1
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from fork-point; and not __fish_seen_subcommand_from --inferred --unset-override --override-to --override-to-inferred --override-to-parent" -f -l inferred
# form 2
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from fork-point; and not __fish_seen_subcommand_from --inferred --unset-override --override-to --override-to-inferred --override-to-parent" -x -l override-to
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from fork-point; and not __fish_seen_subcommand_from --inferred --unset-override --override-to --override-to-inferred --override-to-parent" -f -l override-to-inferred
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from fork-point; and not __fish_seen_subcommand_from --inferred --unset-override --override-to --override-to-inferred --override-to-parent" -f -l override-to-parent
# form 3
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from fork-point; and not __fish_seen_subcommand_from --inferred --unset-override --override-to --override-to-inferred --override-to-parent" -f -l unset-override

# git machete github
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands" -f -a github -d 'Create, check out and manage GitHub PRs while keeping them reflected in git machete'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from github; and not __fish_seen_subcommand_from anno-prs checkout-prs create-pr retarget-pr sync"        -f -a anno-prs     -d 'Annotates the branches based on their corresponding GitHub PR numbers and authors'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from github; and not __fish_seen_subcommand_from anno-prs checkout-prs create-pr retarget-pr sync"        -x -a checkout-prs -d 'Check out the head branch of the given pull requests (specified by number), also traverse chain of pull requests upwards, adding branches one by one to git-machete and check them out locally'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from github; and not __fish_seen_subcommand_from anno-prs checkout-prs create-pr retarget-pr sync"        -f -a create-pr    -d 'Creates a PR for the current branch, using the upstream (parent) branch as the PR base'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from github; and not __fish_seen_subcommand_from anno-prs checkout-prs create-pr retarget-pr sync"        -f -a retarget-pr  -d 'Sets the base of the current branch\'s PR to upstream (parent) branch, as seen by git machete (see git machete show up)'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from github; and not __fish_seen_subcommand_from anno-prs checkout-prs create-pr retarget-pr sync"        -f -a sync         -d 'Synchronize with the remote repository: checkout open PRs for the current user associated with the GitHub token, delete unmanaged branches and also delete untracked managed branches with no downstream branch'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from github; and __fish_seen_subcommand_from checkout-prs; and not __fish_seen_subcommand_from --all"     -f -l all          -d 'Checkout all open PRs'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from github; and __fish_seen_subcommand_from checkout-prs; and not __fish_seen_subcommand_from --by"      -f -l by           -d "Checkout someone's open PRs"
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from github; and __fish_seen_subcommand_from checkout-prs; and not __fish_seen_subcommand_from --mine"    -f -l mine         -d 'Checkout open PRs for the current user associated with the GitHub token'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from github; and __fish_seen_subcommand_from create-pr; and not __fish_seen_subcommand_from --draft"      -f -l draft        -d 'Creates the new PR as a draft'

# git machete go
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands" -f -a go -d 'Check out the branch relative to the position of the current branch, accepts down/first/last/next/root/prev/up argument'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from go g; and not __fish_seen_subcommand_from down d first f last l next n prev p root r up u" -f -a down  -d 'the direct children/downstream branch of the current branch'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from go g; and not __fish_seen_subcommand_from down d first f last l next n prev p root r up u" -f -a first -d 'the first downstream of the root branch of the current branch (like root followed by next), or the root branch itself if the root has no downstream branches'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from go g; and not __fish_seen_subcommand_from down d first f last l next n prev p root r up u" -f -a last  -d 'the last branch in the definition file that has the same root as the current branch; can be the root branch itself if the root has no downstream branches'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from go g; and not __fish_seen_subcommand_from down d first f last l next n prev p root r up u" -f -a next  -d 'the direct successor of the current branch in the definition file'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from go g; and not __fish_seen_subcommand_from down d first f last l next n prev p root r up u" -f -a prev  -d 'the direct predecessor of the current branch in the definition file'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from go g; and not __fish_seen_subcommand_from down d first f last l next n prev p root r up u" -f -a root  -d 'the root of the tree where the current branch is located. Note: this will typically be something like develop or master, since all branches are usually meant to be ultimately merged to one of those'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from go g; and not __fish_seen_subcommand_from down d first f last l next n prev p root r up u" -f -a up    -d 'the direct parent/upstream branch of the current branch'

# git machete help
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands" -f -a help -d 'Display overview, or detailed help for a specified command'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from help" -f -a "$__mcht_help_topics"
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from help" -f -a "(complete -C 'git machete ')"

# git machete is-managed
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands" -f -a is-managed -d 'Check if the current branch is managed by git machete (mostly for scripts)'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from is-managed"           -f -a '(__fish_git_local_branches)'

# git machete list
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands" -f -a list -d 'List all branches that fall into one of pre-defined categories (mostly for internal use)'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from list; and not __fish_seen_subcommand_from addable managed slidable slidable-after unmanaged with-overridden-fork-point" -f -a addable                    -d 'all branches (local or remote) than can be added to the definition file'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from list; and not __fish_seen_subcommand_from addable managed slidable slidable-after unmanaged with-overridden-fork-point" -f -a managed                    -d 'all branches that appear in the definition file'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from list; and not __fish_seen_subcommand_from addable managed slidable slidable-after unmanaged with-overridden-fork-point" -f -a slidable                   -d 'all managed branches that have an upstream and can be slid out with slide-out command'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from list; and not __fish_seen_subcommand_from addable managed slidable slidable-after unmanaged with-overridden-fork-point" -f -a slidable-after             -d 'the downstream branch of the <branch>, if it exists and is the only downstream of <branch> (i.e. the one that can be slid out immediately following <branch>)'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from list; and __fish_seen_subcommand_from slidable-after" -f -a '(__fish_git_local_branches)'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from list; and not __fish_seen_subcommand_from addable managed slidable slidable-after unmanaged with-overridden-fork-point" -f -a unmanaged                  -d 'all local branches that don\'t appear in the definition file'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from list; and not __fish_seen_subcommand_from addable managed slidable slidable-after unmanaged with-overridden-fork-point" -f -a with-overridden-fork-point -d 'all local branches that have a fork point override set up (even if this override does not affect the location of their fork point anymore).'

# git machete log
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands" -f -a log -d 'Log the part of history specific to the given branch'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from log" -f -a '(__fish_git_local_branches)'

# git machete reapply
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands" -f -a reapply -d 'Rebase the current branch onto its computed fork point'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from reapply" -x -l fork-point -s f -a '(__fish_git_local_branches)' -d 'Specifies the alternative fork point commit after which the rebased part of history is meant to start'

# git machete show
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands" -f -a show -d 'Show name(s) of the branch(es) relative to the position of a branch, accepts down/first/last/next/root/prev/up argument'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from show; and not __fish_seen_subcommand_from current c down d first f last l next n prev p root r up u" -f -a 'current c' -d 'the current branch; exits with a non-zero status if none (detached HEAD)'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from show; and not __fish_seen_subcommand_from current c down d first f last l next n prev p root r up u" -f -a 'down d'    -d 'the direct children/downstream branch of the given branch'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from show; and not __fish_seen_subcommand_from current c down d first f last l next n prev p root r up u" -f -a 'first f'   -d 'the first downstream of the root branch of the given branch (like root followed by next), or the root branch itself if the root has no downstream branches'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from show; and not __fish_seen_subcommand_from current c down d first f last l next n prev p root r up u" -f -a 'last l'    -d 'the last branch in the definition file that has the same root as the given branch; can be the root branch itself if the root has no downstream branches'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from show; and not __fish_seen_subcommand_from current c down d first f last l next n prev p root r up u" -f -a 'next n'    -d 'the direct successor of the given branch in the definition file'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from show; and not __fish_seen_subcommand_from current c down d first f last l next n prev p root r up u" -f -a 'prev p'    -d 'the direct predecessor of the given branch in the definition file'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from show; and not __fish_seen_subcommand_from current c down d first f last l next n prev p root r up u" -f -a 'root r'    -d 'the root of the tree where the given branch is located'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from show; and not __fish_seen_subcommand_from current c down d first f last l next n prev p root r up u" -f -a 'up u'      -d 'the direct parent/upstream branch of the given branch'

# git machete slide-out
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands" -f -a slide-out -d 'Slide out the current branch and sync its downstream (child) branches with its upstream (parent) branch via rebase or merge'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from slide-out; and not __fish_seen_subcommand_from --merge -M --down-fork-point -d"                                                        -x -l down-fork-point -s d  -d 'If updating by rebase, specifies the alternative fork point for downstream branches for the operation. git machete fork-point overrides for downstream branches are recommended over use of this option. See also doc for --fork-point option in git machete help reapply and git machete help update. Not allowed if updating by merge'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from slide-out; and not __fish_seen_subcommand_from --delete"                                                                               -f -l delete                -d 'Delete branches from git'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from slide-out; and not __fish_seen_subcommand_from --merge -M --down-fork-point -d"                                                        -f -l merge           -s M  -d 'Update the downstream branch by merge rather than by rebase'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from slide-out; and not __fish_seen_subcommand_from -n --no-edit-merge --no-interactive-rebase"                                             -f                    -s n  -d 'If updating by rebase, equivalent to --no-interactive-rebase. If updating by merge, equivalent to --no-edit-merge'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from slide-out; and not __fish_seen_subcommand_from -n --no-edit-merge --no-interactive-rebase; and __fish_seen_subcommand_from --merge -M" -f -l no-edit-merge         -d 'If updating by merge, skip opening the editor for merge commit message while doing git merge (i.e. pass --no-edit flag to underlying git merge). Not allowed if updating by rebase'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from slide-out; and not __fish_seen_subcommand_from -n --no-edit-merge --no-interactive-rebase -M --merge"                                  -f -l no-interactive-rebase -d 'If updating by rebase, run git rebase in non-interactive mode (without -i/--interactive flag). Not allowed if updating by merge'

# git machete squash
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands" -f -a squash -d 'Squash the unique history of the current branch into a single commit'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from squash" -x -l fork-point -s f -a '(__fish_git_local_branches)' -d 'Specifies the alternative fork point commit after which the squashed part of history is meant to start'

# git machete status
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands" -f -a status -d 'Display formatted tree of branch dependencies, including info on their sync with upstream branch and with remote'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from status s; and not __fish_seen_subcommand_from --color"                       -f -l color                    -a "auto always never" -d 'Colorize the output (default: auto)'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from status s; and not __fish_seen_subcommand_from --list-commits -l"             -f -l list-commits             -s l                   -d 'Additionally list the commits introduced on each branch'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from status s; and not __fish_seen_subcommand_from --list-commits-with-hashes -L" -f -l list-commits-with-hashes -s L                   -d 'Additionally list the short hashes and messages of commits introduced on each branch'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from status s; and not __fish_seen_subcommand_from --no-detect-squash-merges"     -f -l no-detect-squash-merges                         -d 'Only consider "strict" (fast-forward or 2-parent) merges, rather than rebase/squash merges, when detecting if a branch is merged into its upstream (parent)'

# git machete traverse
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands" -f -a traverse -d 'Walk through the tree of branch dependencies and rebase, merge, slide out, push and/or pull each branch one by one'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --fetch -F"                -f -l fetch        -s F -d 'Fetch the remotes of all managed branches at the beginning of traversal (no git pull involved, only git fetch)'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --list-commits -l"         -f -l list-commits -s l -d 'When printing the status, additionally list the messages of commits introduced on each branch'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --merge -M"                -f -l merge        -s M -d 'Update by merge rather than by rebase'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --yes -y"                  -f                 -s n -d 'If updating by rebase, equivalent to --no-interactive-rebase. If updating by merge, equivalent to --no-edit-merge'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --no-detect-squash-merges" -f -l no-detect-squash-merges -d 'Only consider "strict" (fast-forward or 2-parent) merges, rather than rebase/squash merges, when detecting if a branch is merged into its upstream (parent)'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --no-edit-merge; and __fish_seen_subcommand_from --merge -M"             -f -l no-edit-merge         -d 'If updating by merge, skip opening the editor for merge commit message while doing git merge (i.e. pass --no-edit flag to underlying git merge). Not allowed if updating by rebase'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --no-interactive-rebase; and not __fish_seen_subcommand_from --merge -M" -f -l no-interactive-rebase -d 'If updating by rebase, run git rebase in non-interactive mode (without -i/--interactive flag). Not allowed if updating by merge'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --no-push"           -f -l no-push           -d 'Do not push any (neither tracked nor untracked) branches to remote, re-enable via --push'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --no-push-untracked" -f -l no-push-untracked -d 'Do not push untracked branches to remote, re-enable via --push-untracked'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --push"              -f -l push              -d 'Push all (both tracked and untracked) branches to remote - default behavior'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --push-untracked"    -f -l push-untracked    -d 'Push untracked branches to remote - default behavior'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --return-to"         -x -l return-to  -a 'stay here nearest-remaining' -d 'Specifies the branch to return after traversal is successfully completed; WHERE can be here (the current branch at the moment when traversal starts), nearest-remaining (nearest remaining branch in case the here branch has been slid out by the traversal) or stay (the default - just stay wherever the traversal stops). Note: when user quits by q/yq or when traversal is stopped because one of git actions fails, the behavior is always stay'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --start-from"        -x -l start-from -a 'here root first-root'        -d 'Specifies the branch to start the traversal from; WHERE can be here (the default - current branch, must be managed by git-machete), root (root branch of the current branch, as in git machete show root) or first-root (first listed managed branch)'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --whole -w"          -f -l whole      -s w                             -d 'Equivalent to -n --start-from=first-root --return-to=nearest-remaining; useful for quickly traversing & syncing all branches (rather than doing more fine-grained operations on the local section of the branch tree)'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from -W"                  -f               -s W                             -d 'Equivalent to --fetch --whole; useful for even more automated traversal of all branches'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --yes -y"            -f -l yes        -s y                             -d 'Don\'t ask for any interactive input, including confirmation of rebase/push/pull. Implies -n'

# git machete update
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands" -f -a update -d 'Sync the current branch with its upstream (parent) branch via rebase or merge'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from update; and not __fish_seen_subcommand_from --merge -M"                                            -x -l fork-point -s f -a '(__fish_git_local_branches)' -d 'If updating by rebase, specifies the alternative fork point commit after which the rebased part of history is meant to start. Not allowed if updating by merge'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from update; and not __fish_seen_subcommand_from -n --no-edit-merge --no-interactive-rebase"            -f               -s n                                  -d 'If updating by rebase, equivalent to --no-interactive-rebase. If updating by merge, equivalent to --no-edit-merge'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from update; and not __fish_seen_subcommand_from -n --no-edit-merge --no-interactive-rebase"            -f -l no-edit-merge                                    -d 'If updating by merge, skip opening the editor for merge commit message while doing git merge (i.e. pass --no-edit flag to underlying git merge)'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from update; and not __fish_seen_subcommand_from -n --no-edit-merge --no-interactive-rebase -M --merge" -f -l no-interactive-rebase                            -d 'If updating by rebase, run git rebase in non-interactive mode (without -i/--interactive flag). Not allowed if updating by merge'
complete -c git -n "__fish_git_using_command machete; and __fish_seen_subcommand_from update; and not __fish_seen_subcommand_from --merge -M"                                            -f -l merge      -s M                                  -d 'Update by merge rather than by rebase'

# git machete version
complete -c git -n "__fish_git_using_command machete; and not __fish_seen_subcommand_from $__mcht_commands" -f -a version -d 'Display the version and exit'
