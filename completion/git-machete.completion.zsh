#compdef git-machete

_git-machete() {
    local ret=1

    _arguments -C \
        '1: :__git_machete_commands' \
        '*::arg:->args' \
        '(--debug)'--debug'[Log detailed diagnostic info, including outputs of the executed git commands]' \
        '(-h --help)'{-h,--help}'[Print help and exit]' \
        '(-v --verbose)'{-v,--verbose}'[Log the executed git commands]' \
        '(--version)'--version'[Print version and exit]' \
    && ret=0

    case $state in
        (args)
            case ${line[1]} in
                (add)
                    _arguments \
                        '1:: :__git_machete_list_addable' \
                        '(-o --onto)'{-o,--onto=}'[Specify the target parent branch to add the given branch onto]: :__git_machete_list_managed' \
                        '(-R --as-root)'{-R,--as-root}'[Add the given branch as a new root]' \
                        '(-y --yes)'{-y,--yes}'[Do not ask for confirmation whether to create the branch or whether to add onto the inferred upstream]' \
                    && ret=0
                    ;;
                (advance|delete-unmanaged)
                    _arguments \
                        '(-y --yes)'{-y,--yes}'[Do not ask for confirmation]' \
                    && ret=0
                    ;;
                (anno)
                    _arguments \
                        '(-b --branch)'{-b,--branch=}'[Branch to set the annotation for]: :__git_machete_list_managed' \
                    && ret=0
                    ;;
                (d|diff)
                    _arguments \
                        '1:: :__git_branch_names' \
                        '(-s --stat)'{-s,--stat}'[Pass --stat option to git diff, so that only summary (diffstat) is printed]' \
                    && ret=0
                    ;;
                (discover)
                    # TODO complete the comma-separated list of roots
                    _arguments \
                        '(-C --checked-out-since)'{-C,--checked-out-since=}'[Only consider branches checked out at least once since the given date]' \
                        '(-l --list-commits)'{-l,--list-commits}'[List the messages of commits introduced on each branch]' \
                        '(-r --roots)'{-r,--roots=}'[Comma-separated list of branches to be considered roots of trees of branch dependencies (typically develop and/or master)]: :__git_branch_names' \
                        '(-y --yes)'{-y,--yes}'[Do not ask for confirmation]' \
                    && ret=0
                    ;;
                (e|edit|file)
                    ;;
                (fork-point)
                    # TODO correctly suggest branches for `--unset-override`
                    _arguments '1:: :__git_branch_names' \
                        '(--inferred)'--inferred'[Display the fork point ignoring any potential override]' \
                        '(--override-to)'--override-to='[Override fork point to the given revision]: :__git_references' \
                        '(--override-to-inferred)'--override-to-inferred'[Override fork point to the inferred location]' \
                        '(--override-to-parent)'--override-to-parent'[Override fork point to the upstream (parent) branch]' \
                        '(--unset-override)'--unset-override'[Unset fork point override by removing machete.overrideForkPoint.<branch>.* configs]' \
                    && ret=0
                    ;;
                (g|go)
                    _arguments '1:: :__git_machete_directions_go' && ret=0
                    ;;
                (help)
                    _arguments '1:: :__git_machete_help_topics' && ret=0
                    ;;
                (is-managed|l|log)
                    _arguments '1:: :__git_branch_names' && ret=0
                    ;;
                (list)
                    _arguments '1:: :__git_machete_categories' && ret=0
                    ;;
                (reapply)
                    _arguments \
                        '(-f --fork-point)'{-f,--fork-point=}'[Fork point commit after which the rebased part of history is meant to start]: :__git_references' \
                    && ret=0
                    ;;
                (show)
                    _arguments '1:: :__git_machete_directions_show' && ret=0
                    ;;
                (slide-out)
                    _arguments \
                        # TODO suggest further branches based on the previous specified branch (like in Bash completion script)
                        '*:: :__git_machete_list_slidable' \
                        '(-d --down-fork-point)'{-d,--down-fork-point=}'[If updating by rebase, specify fork point commit after which the rebased part of history of the downstream branch is meant to start]: :__git_references' \
                        '(-M --merge)'{-M,--merge}'[Update by merge rather than by rebase]' \
                        '(-n)'-n'[If updating by rebase, equivalent to --no-interactive-rebase. If updating by merge, equivalent to --no-edit-merge]' \
                        '(--no-edit-merge)'--no-edit-merge'[If updating by merge, pass --no-edit flag to underlying git merge]' \
                        '(--no-interactive-rebase)'--no-interactive-rebase'[If updating by rebase, do NOT pass --interactive flag to underlying git rebase]' \
                    && ret=0
                    ;;
                (s|status)
                    _arguments \
                        '(--color)'--color='[Colorize the output; argument can be "always", "auto", or "never"]: :__git_machete_opt_color_args' \
                        '(-L --list-commits-with-hashes)'{-L,--list-commits-with-hashes}'[List the short hashes and messages of commits introduced on each branch]' \
                        '(-l --list-commits)'{-l,--list-commits}'[List the messages of commits introduced on each branch]' \
                    && ret=0
                    ;;
                (traverse)
                    _arguments \
                        '(-F --fetch)'{-F,--fetch}'[Fetch the remotes of all managed branches at the beginning of traversal]' \
                        '(-l --list-commits)'{-l,--list-commits}'[List the messages of commits introduced on each branch]' \
                        '(-M --merge)'{-M,--merge}'[Update by merge rather than by rebase]' \
                        '(-n)'-n'[If updating by rebase, equivalent to --no-interactive-rebase. If updating by merge, equivalent to --no-edit-merge]' \
                        '(--no-edit-merge)'--no-edit-merge'[If updating by merge, pass --no-edit flag to underlying git merge]' \
                        '(--no-interactive-rebase)'--no-interactive-rebase'[If updating by rebase, do NOT pass --interactive flag to underlying git rebase]' \
                        '(--return-to)'--return-to='[The branch to return after traversal is successfully completed; argument can be "here", "nearest-remaining", or "stay"]: :__git_machete_opt_return_to_args' \
                        '(--start-from)'--start-from='[The branch to  to start the traversal from; argument can be "here", "root", or "first-root"]: :__git_machete_opt_start_from_args' \
                        '(-w --whole)'{-w,--whole}'[Equivalent to -n --start-from=first-root --return-to=nearest-remaining]' \
                        '(-W)'-W'[Equivalent to --fetch --whole]' \
                        '(-y --yes)'{-y,--yes}'[Do not ask for any interactive input; implicates -n]' \
                    && ret=0
                    ;;
                 (update)
                    _arguments \
                        '(-f --fork-point)'{-f,--fork-point=}'[If updating by rebase, specify fork point commit after which the rebased part of history is meant to start]: :__git_references' \
                        '(-M --merge)'{-M,--merge}'[Update by merge rather than by rebase]' \
                        '(-n)'-n'[If updating by rebase, equivalent to --no-interactive-rebase. If updating by merge, equivalent to --no-edit-merge]' \
                        '(--no-edit-merge)'--no-edit-merge'[If updating by merge, pass --no-edit flag to underlying git merge]' \
                        '(--no-interactive-rebase)'--no-interactive-rebase'[If updating by rebase, do NOT pass --interactive flag to underlying git rebase]' \
                    && ret=0
                    ;;
            esac
    esac
}

__git_machete_cmds=(
    'add:Add a branch to the tree of branch dependencies'
    'advance:Fast-forward the current branch to match one of its downstreams and subsequently slide out this downstream'
    'anno:Manage custom annotations'
    'delete-unmanaged:Delete local branches that are not present in the definition file'
    {diff,d}':Diff current working directory or a given branch against its fork point'
    'discover:Automatically discover tree of branch dependencies'
    {edit,e}':Edit the definition file'
    'file:Display the location of the definition file'
    'fork-point:Display SHA of the fork point commit of a branch'
    {go,g}':Check out the branch relative to the position of the current branch'
    'help:Display this overview, or detailed help for a specified command'
    'is-managed:Check if the current branch is managed by git-machete (mostly for scripts)'
    'list:List all branches that fall into one of pre-defined categories (mostly for internal use)'
    {log,l}':Log the part of history specific to the given branch'
    'reapply:Rebase the current branch onto its own fork point'
    'show:Show name(s) of the branch(es) relative to the position of the current branch'
    'slide-out:Slide the current branch out and sync its downstream (child) branch with its upstream (parent) branch via rebase or merge'
    {status,s}':Display formatted tree of branch dependencies, including info on their sync with upstream branch and with remote'
    'traverse:Walk through the tree of branch dependencies and rebase, merge, slide out, push and/or pull each branch one by one'
    'update:Sync the current branch with its upstream (parent) branch via rebase or merge'
    'version:Display version and exit'
)

__git_machete_commands() {
    _describe -t __git_machete_cmds 'git machete command' __git_machete_cmds "$@"
}

__git_machete_help_topics() {
    local topics
    set -A topics ${__git_machete_cmds}
    topics+=(
        'format:Format of the .git/machete definition file'
        'hooks:Display docs for the extra hooks added by git machete'
    )
    _describe -t topics 'git machete help topic' topics "$@"
}

__git_machete_directions_go() {
    local directions
    directions=(
        {d,down}':child(ren) in tree of branch dependencies'
        {f,first}':first child of the current root branch'
        {l,last}':last branch located under current root branch'
        {n,next}':the one defined in the following line in .git/machete file'
        {p,prev}':the one defined in the preceding line in .git/machete file'
        {r,root}':root of the tree of branch dependencies where current branch belongs'
        {u,up}':parent in tree of branch dependencies'
    )
    _describe -t directions 'direction' directions "$@"
}

# TODO extract the part shared with __git_machete_go_directions
__git_machete_directions_show() {
    local directions
    directions=(
        {c,current}':the currently checked out branch'
        {d,down}':child(ren) in tree of branch dependencies'
        {f,first}':first child of the current root branch'
        {l,last}':last branch located under current root branch'
        {n,next}':the one defined in the following line in .git/machete file'
        {p,prev}':the one defined in the preceding line in .git/machete file'
        {r,root}':root of the tree of branch dependencies where current branch belongs'
        {u,up}':parent in tree of branch dependencies'
    )
    _describe -t directions 'direction' directions "$@"
}

__git_machete_categories() {
    local categories
    # TODO complete slidable-after's argument
    categories=(
        'addable:all branches (local or remote) than can be added to the definition file'
        'managed:all branches that appear in the definition file'
        'slidable:all managed branches that have exactly one upstream and one downstream (i.e. the ones that can be slid out with slide-out command)'
        'slidable-after:the downstream branch of the given branch, if it exists and is its only downstream (i.e. the one that can be slid out immediately following <branch>)'
        'unmanaged:all local branches that do not appear in the definition file'
        'with-overridden-fork-point:all local branches that have a fork point override config'
    )
    _describe -t categories 'category' categories "$@"
}

__git_machete_opt_color_args() {
    local opt_color_args
    opt_color_args=(
        'always:always emits colors'
        'auto:emits colors only when standard output is connected to a terminal'
        'never:colors are disabled'
    )
    _describe -t opt_color_args 'color argument' opt_color_args "$@"
}

__git_machete_opt_return_to_args() {
    local opt_return_to
    opt_return_to=(
        'here:the current branch at the moment when traversal starts'
        'nearest-remaining:nearest remaining branch in case the "here" branch has been slid out by the traversal'
        'stay:the default - just stay wherever the traversal stops'
    )
    _describe -t opt_return_to 'return-to argument' opt_return_to "$@"
}

__git_machete_opt_start_from_args() {
    local opt_start_from
    opt_start_from=(
        'here:the default - current branch, must be managed by git-machete'
        'root:root branch of the current branch, as in git machete show root'
        'first-root:first listed managed branch'
    )
    _describe -t opt_start_from 'start-from argument' opt_start_from "$@"
}

__git_machete_list_addable() {
    local list_addable
    IFS=$'\n' list_addable=($(git machete list addable 2>/dev/null))
    _describe -t list_addable 'addable branch' list_addable "$@"
}

__git_machete_list_managed() {
    local list_managed
    IFS=$'\n' list_managed=($(git machete list managed 2>/dev/null))
    _describe -t list_managed 'managed branch' list_managed "$@"
}

__git_machete_list_slidable() {
    local list_slidable
    IFS=$'\n' list_slidable=($(git machete list slidable 2>/dev/null))
    _describe -t list_slidable 'slidable branch' list_slidable "$@"
}

zstyle ':completion:*:*:git:*' user-commands machete:'organize your repo, instantly rebase/merge/push/pull and more'
