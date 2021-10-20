set -l __mcht_commands \
    add       \
    discover  \
    edit e    \
    go g      \
    help      \
    slide-out \
    status s  \
    traverse  \
    update    \
    version

# TODO: completion for all commands:
    # advance
    # anno
    # delete-unmanaged
    # diff d
    # file
    # fork-point
    # format
    # github
    # hooks
    # is-managed
    # list
    # log l
    # reapply
    # show
    # squash

# git
complete --command git --condition "not __fish_seen_subcommand_from machete" --no-files --arguments machete --description 'Tool for managing git workflows'
complete --command git --condition "__fish_seen_subcommand_from machete" --no-files # (suppress file completion)

# git machete (general options)
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from $__mcht_commands; and not __fish_seen_subcommand_from --help -h" --no-files --short-option h --long-option help --description 'Print help and exit'
#                     Parameters -h/--help work for subcommands only. ---^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#                     See: https://github.com/VirtusLab/git-machete/issues/25
complete --command git --condition "__fish_seen_subcommand_from machete; and not __fish_seen_subcommand_from --verbose -v" --no-files --long-option verbose --short-option v --description 'Log the executed git commands'
complete --command git --condition "__fish_seen_subcommand_from machete; and not __fish_seen_subcommand_from --debug"      --no-files --long-option debug                    --description 'Log detailed diagnostic info, including outputs of the executed git commands'
complete --command git --condition "__fish_seen_subcommand_from machete; and not __fish_seen_subcommand_from --version"    --no-files --long-option version                  --description 'Print version and exit'

# git machete add
complete --command git --condition "__fish_seen_subcommand_from machete; and not __fish_seen_subcommand_from $__mcht_commands" --no-files --arguments add --description 'Add a branch to the tree of branch dependencies'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from add; and not __fish_seen_subcommand_from --as-root -R --onto -o" --no-files --long-option onto    --short-option o --require-parameter --description 'Specifies the target parent branch to add the given branch onto. Cannot be specified together with -R/--as-root'
# ^ TODO: arguments
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from add; and not __fish_seen_subcommand_from --onto -o --as-root -R" --no-files --long-option as-root --short-option R                     --description 'Add the given branch as a new root (and not onto any other branch). Cannot be specified together with -o/--onto'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from add; and not __fish_seen_subcommand_from --yes -y"               --no-files --long-option yes     --short-option y                     --description 'Don\'t ask for confirmation whether to create the branch or whether to add onto the inferred upstream'

# git machete discover
complete --command git --condition "__fish_seen_subcommand_from machete; and not __fish_seen_subcommand_from $__mcht_commands" --no-files --arguments discover --description 'Automatically discover tree of branch dependencies'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from discover; and not __fish_seen_subcommand_from --checked-out-since -C" --no-files --long-option checked-out-since --short-option C --require-parameter --description 'Only consider branches checked out at least once since the given date. <date> can be e.g. 2 weeks ago or 2020-06-01, as in git log --since=<date>. If not present, the date is selected automatically so that around 10 branches are included'
# ^ TODO: arguments
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from discover; and not __fish_seen_subcommand_from --list-commits -l"      --no-files --long-option list-commits      --short-option l                     --description 'When printing the discovered tree, additionally lists the messages of commits introduced on each branch (as for git machete status)'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from discover; and not __fish_seen_subcommand_from --roots -r"             --no-files --long-option roots             --short-option r --require-parameter --description 'Comma-separated list of branches that should be considered roots of trees of branch dependencies. If not present, master is assumed to be a root. Note that in the process of discovery, certain other branches can also be additionally deemed to be roots as well'
# ^ TODO: arguments
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from discover; and not __fish_seen_subcommand_from --yes -y"               --no-files --long-option yes               --short-option y                     --description 'Don\'t ask for confirmation before saving the newly-discovered tree. Mostly useful in scripts; not recommended for manual use'

# git machete edit
complete --command git --condition "__fish_seen_subcommand_from machete; and not __fish_seen_subcommand_from $__mcht_commands" --no-files --arguments edit --description 'Edit the definition file'

# git machete go
complete --command git --condition "__fish_seen_subcommand_from machete; and not __fish_seen_subcommand_from $__mcht_commands" --no-files --arguments go --description 'Check out the branch relative to the position of the current branch, accepts down/first/last/next/root/prev/up argument'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from go g; and not __fish_seen_subcommand_from down d first f last l next n prev p root r up u" --no-files --arguments down  --description 'the direct children/downstream branch of the current branch'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from go g; and not __fish_seen_subcommand_from down d first f last l next n prev p root r up u" --no-files --arguments first --description 'the first downstream of the root branch of the current branch (like root followed by next), or the root branch itself if the root has no downstream branches'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from go g; and not __fish_seen_subcommand_from down d first f last l next n prev p root r up u" --no-files --arguments last  --description 'the last branch in the definition file that has the same root as the current branch; can be the root branch itself if the root has no downstream branches'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from go g; and not __fish_seen_subcommand_from down d first f last l next n prev p root r up u" --no-files --arguments next  --description 'the direct successor of the current branch in the definition file'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from go g; and not __fish_seen_subcommand_from down d first f last l next n prev p root r up u" --no-files --arguments prev  --description 'the direct predecessor of the current branch in the definition file'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from go g; and not __fish_seen_subcommand_from down d first f last l next n prev p root r up u" --no-files --arguments root  --description 'the root of the tree where the current branch is located. Note: this will typically be something like develop or master, since all branches are usually meant to be ultimately merged to one of those'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from go g; and not __fish_seen_subcommand_from down d first f last l next n prev p root r up u" --no-files --arguments up    --description 'the direct parent/upstream branch of the current branch'

# git machete help
complete --command git --condition "__fish_seen_subcommand_from machete; and not __fish_seen_subcommand_from $__mcht_commands" --no-files --arguments help --description 'Display overview, or detailed help for a specified command'

# git machete slide-out 
complete --command git --condition "__fish_seen_subcommand_from machete; and not __fish_seen_subcommand_from $__mcht_commands" --no-files --arguments slide-out --description 'Slide out the current branch and sync its downstream (child) branches with its upstream (parent) branch via rebase or merge'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from slide-out; and not __fish_seen_subcommand_from --merge -M --down-fork-point -d"                                --no-files --long-option down-fork-point --short-option d --require-parameter --description 'If updating by rebase, specifies the alternative fork point for downstream branches for the operation. git machete fork-point overrides for downstream branches are recommended over use of this option. See also doc for --fork-point option in git machete help reapply and git machete help update. Not allowed if updating by merge'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from slide-out; and not __fish_seen_subcommand_from --merge -M"                                                     --no-files --long-option merge           --short-option M                     --description 'Update the downstream branch by merge rather than by rebase'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from slide-out; and not __fish_seen_subcommand_from -n --no-edit-merge --no-interactive-rebase"                     --no-files                               --short-option n                     --description 'If updating by rebase, equivalent to --no-interactive-rebase. If updating by merge, equivalent to --no-edit-merge'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from slide-out; and not __fish_seen_subcommand_from -n --no-edit-merge --no-interactive-rebase; and     __fish_seen_subcommand_from --merge -M" --no-files --long-option no-edit-merge            --description 'If updating by merge, skip opening the editor for merge commit message while doing git merge (i.e. pass --no-edit flag to underlying git merge). Not allowed if updating by rebase'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from slide-out; and not __fish_seen_subcommand_from -n --no-edit-merge --no-interactive-rebase; and not __fish_seen_subcommand_from -M --merge" --no-files --long-option no-interactive-rebase    --description 'If updating by rebase, run git rebase in non-interactive mode (without -i/--interactive flag). Not allowed if updating by merge'

# git machete status
complete --command git --condition "__fish_seen_subcommand_from machete; and not __fish_seen_subcommand_from $__mcht_commands" --no-files --arguments status --description 'Display formatted tree of branch dependencies, including info on their sync with upstream branch and with remote'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from status s; and not __fish_seen_subcommand_from --color"                       --no-files --long-option color                    --arguments "auto always never" --description 'Colorize the output (default: auto)'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from status s; and not __fish_seen_subcommand_from --list-commits -l"             --no-files --long-option list-commits             --short-option l                --description 'Additionally list the commits introduced on each branch'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from status s; and not __fish_seen_subcommand_from --list-commits-with-hashes -L" --no-files --long-option list-commits-with-hashes --short-option L                --description 'Additionally list the short hashes and messages of commits introduced on each branch'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from status s; and not __fish_seen_subcommand_from --no-detect-squash-merges"     --no-files --long-option no-detect-squash-merges                                  --description 'Only consider "strict" (fast-forward or 2-parent) merges, rather than rebase/squash merges, when detecting if a branch is merged into its upstream (parent)'

# git machete traverse
complete --command git --condition "__fish_seen_subcommand_from machete; and not __fish_seen_subcommand_from $__mcht_commands" --no-files --arguments traverse --description 'Walk through the tree of branch dependencies and rebase, merge, slide out, push and/or pull each branch one by one'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --fetch -F"                --no-files --long-option fetch        --short-option F --description 'Fetch the remotes of all managed branches at the beginning of traversal (no git pull involved, only git fetch)'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --list-commits -l"         --no-files --long-option list-commits --short-option l --description 'When printing the status, additionally list the messages of commits introduced on each branch'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --merge -M"                --no-files --long-option merge        --short-option M --description 'Update by merge rather than by rebase'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --yes -y"                  --no-files                            --short-option n --description 'If updating by rebase, equivalent to --no-interactive-rebase. If updating by merge, equivalent to --no-edit-merge'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --no-detect-squash-merges" --no-files --long-option no-detect-squash-merges       --description 'Only consider "strict" (fast-forward or 2-parent) merges, rather than rebase/squash merges, when detecting if a branch is merged into its upstream (parent)'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --no-edit-merge; and __fish_seen_subcommand_from --merge -M"             --no-files --long-option no-edit-merge         --description 'If updating by merge, skip opening the editor for merge commit message while doing git merge (i.e. pass --no-edit flag to underlying git merge). Not allowed if updating by rebase'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --no-interactive-rebase; and not __fish_seen_subcommand_from --merge -M" --no-files --long-option no-interactive-rebase --description 'If updating by rebase, run git rebase in non-interactive mode (without -i/--interactive flag). Not allowed if updating by merge'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --no-push"           --no-files --long-option no-push           --description 'Do not push any (neither tracked nor untracked) branches to remote, re-enable via --push'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --no-push-untracked" --no-files --long-option no-push-untracked --description 'Do not push untracked branches to remote, re-enable via --push-untracked'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --push"              --no-files --long-option push              --description 'Push all (both tracked and untracked) branches to remote - default behavior'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --push-untracked"    --no-files --long-option push-untracked    --description 'Push untracked branches to remote - default behavior'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --return-to"         --no-files --long-option return-to  --require-parameter --arguments 'stay here nearest-remaining' --description 'Specifies the branch to return after traversal is successfully completed; WHERE can be here (the current branch at the moment when traversal starts), nearest-remaining (nearest remaining branch in case the here branch has been slid out by the traversal) or stay (the default - just stay wherever the traversal stops). Note: when user quits by q/yq or when traversal is stopped because one of git actions fails, the behavior is always stay'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --start-from"        --no-files --long-option start-from --require-parameter --arguments 'here root first-root'        --description 'Specifies the branch to start the traversal from; WHERE can be here (the default - current branch, must be managed by git-machete), root (root branch of the current branch, as in git machete show root) or first-root (first listed managed branch)'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --whole -w"          --no-files --long-option whole --short-option w --description 'Equivalent to -n --start-from=first-root --return-to=nearest-remaining; useful for quickly traversing & syncing all branches (rather than doing more fine-grained operations on the local section of the branch tree)'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from -W"                  --no-files                     --short-option W --description 'Equivalent to --fetch --whole; useful for even more automated traversal of all branches'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from traverse; and not __fish_seen_subcommand_from --yes -y"            --no-files --long-option yes   --short-option y --description 'Don\'t ask for any interactive input, including confirmation of rebase/push/pull. Implies -n'

# git machete update
complete --command git --condition "__fish_seen_subcommand_from machete; and not __fish_seen_subcommand_from $__mcht_commands" --no-files --arguments update --description 'Sync the current branch with its upstream (parent) branch via rebase or merge'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from update; and not __fish_seen_subcommand_from --merge -M --fork-point -f" --no-files --long-option fork-point --short-option f --require-parameter --arguments "auto always never" --description 'If updating by rebase, specifies the alternative fork point commit after which the rebased part of history is meant to start. Not allowed if updating by merge'
# ^ TODO: --argument: commits, branches, etc
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from update; and not __fish_seen_subcommand_from -n --no-edit-merge --no-interactive-rebase"            --no-files                                     --short-option n --description 'If updating by rebase, equivalent to --no-interactive-rebase. If updating by merge, equivalent to --no-edit-merge'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from update; and not __fish_seen_subcommand_from -n --no-edit-merge --no-interactive-rebase"            --no-files --long-option no-edit-merge                          --description 'If updating by merge, skip opening the editor for merge commit message while doing git merge (i.e. pass --no-edit flag to underlying git merge)'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from update; and not __fish_seen_subcommand_from -n --no-edit-merge --no-interactive-rebase -M --merge" --no-files --long-option no-interactive-rebase                  --description 'If updating by rebase, run git rebase in non-interactive mode (without -i/--interactive flag). Not allowed if updating by merge'
complete --command git --condition "__fish_seen_subcommand_from machete; and __fish_seen_subcommand_from update; and not __fish_seen_subcommand_from --merge -M"                                            --no-files --long-option merge                 --short-option M --description 'Update by merge rather than by rebase'

# git machete version
complete --command git --condition "__fish_seen_subcommand_from machete; and not __fish_seen_subcommand_from $__mcht_commands" --no-files --arguments version --description 'Display the version and exit'
