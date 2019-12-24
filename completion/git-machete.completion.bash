#!/usr/bin/env bash

_git_machete() {
    cmds="add anno d delete-unmanaged diff discover e edit file fork-point g go help l list log reapply show slide-out s status traverse update version"
    help_topics="$cmds format hooks"

    categories="managed slidable slidable-after unmanaged with-overridden-fork-point"
    directions="down first last next prev root up"
    opt_color_args="always auto never"
    opt_return_to_args="here nearest-remaining stay"
    opt_start_from_args="here root first-root"

    common_opts="--debug -h --help -v --verbose --version"
    add_opts="-o --onto= --yes"
    delete_unmanaged_opts="--yes"
    diff_opts="-s --stat"
    discover_opts="-C --checked-out-since= -l --list-commits -r --roots= -y --yes"
    fork_point_opts="--inferred --override-to= --override-to-inferred --override-to-parent --unset-override"
    reapply_opts="-f --fork-point="
    slide_out_opts="-d --down-fork-point= -M --merge -n --no-edit-merge --no-interactive-rebase"
    status_opts="--color= -L --list-commits-with-hashes -l --list-commits"
    traverse_opts="-F --fetch -l --list-commits -M --merge -n --no-edit-merge --no-interactive-rebase --return-to= --start-from= -w --whole -W --yes"
    update_opts="-f --fork-point= -M --merge -n --no-edit-merge --no-interactive-rebase"

    case $cur in
        --checked-out-since=*) __gitcomp "" ;;
        --color=*) __gitcomp "$opt_color_args" "" "${cur##--color=}" ;;
        --down-fork-point=*|--fork-point=*|--override-to=*) __gitcomp "$(__git_refs)" "" "${cur##--*=}" ;;
        --onto=*) __gitcomp_nl "$(git machete list managed)" "" "${cur##--onto=}" ;;
        --return-to=*) __gitcomp "$opt_return_to_args" "" "${cur##--return-to=}" ;;
        --roots=*) __gitcomp "$(__git_heads)" "" "${cur##--roots=}" ;;
        --start-from=*) __gitcomp "$opt_start_from_args" "" "${cur##--start-from=}" ;;
        -*)
            case ${COMP_WORDS[2]} in
                add) __gitcomp "$common_opts $add_opts" ;;
                d|diff) __gitcomp "$common_opts $diff_opts" ;;
                delete-unmanaged) __gitcomp "$common_opts $delete_unmanaged_opts" ;;
                discover) __gitcomp "$common_opts $discover_opts" ;;
                fork-point) __gitcomp "$common_opts $fork_point_opts" ;;
                reapply) __gitcomp "$common_opts $reapply_opts" ;;
                slide-out) __gitcomp "$common_opts $slide_out_opts" ;;
                s|status) __gitcomp "$common_opts $status_opts" ;;
                traverse) __gitcomp "$common_opts $traverse_opts" ;;
                update) __gitcomp "$common_opts $update_opts" ;;
                *) __gitcomp "$common_opts" ;;
            esac ;;
         *)
             if [[ $COMP_CWORD -eq 2 ]]; then
                __gitcomp "$cmds"
             else
                prev=${COMP_WORDS[COMP_CWORD-1]}
                case $prev in
                    -C|--checked-out-since) __gitcomp "" ;;
                    --color) __gitcomp "$opt_color_args" ;;
                    -d|--down-fork-point|-f|--fork-point|--override-to) __gitcomp "$(__git_refs)" ;;
                    # TODO (GH issue #25): We don't complete --help since it's going to be captured by git anyway
                    # (and results in redirection to yet non-existent man for `git-machete`).
                    -h) __gitcomp "$help_topics" ;;
                    -o|--onto) __gitcomp_nl "$(git machete list managed)" ;;
                    --return-to) __gitcomp "$opt_return_to_args" ;;
                    # TODO complete the comma-separated list of roots
                    -r|--roots) __gitcomp "$(__git_heads)" ;;
                    --start-from) __gitcomp "$opt_start_from_args" ;;
                    --unset-override) __gitcomp_nl "$(git machete list with-overridden-fork-point)" ;;
                    *)
                        case ${COMP_WORDS[2]} in
                            add) __gitcomp_nl "$(git machete list unmanaged)" ;;
                            d|diff|fork-point|l|log) __gitcomp "$(__git_heads)" ;;
                            g|go|show) __gitcomp "$directions" ;;
                            help) __gitcomp "$help_topics" ;;
                            list)
                                if [[ $COMP_CWORD -eq 3 ]]; then
                                    __gitcomp "$categories"
                                elif [[ $COMP_CWORD -eq 4 && $prev == slidable-after ]]; then
                                    __gitcomp_nl "$(git machete list slidable)"
                                fi ;;
                            slide-out)
                                if [[ $COMP_CWORD -eq 3 ]]; then
                                    __gitcomp_nl "$(git machete list slidable)"
                                else
                                    __gitcomp_nl "$(git machete list slidable-after "$prev" 2>/dev/null)"
                                fi ;;
                            *) __gitcomp "" ;;
                        esac ;;
                esac
            fi
    esac
}
