#!/usr/bin/env bash

_git_machete() {
    local cmds="add advance anno d delete-unmanaged diff discover e edit file fork-point g go help is-managed l list log reapply show slide-out s status traverse update version"
    local help_topics="$cmds format hooks"

    local categories="addable managed slidable slidable-after unmanaged with-overridden-fork-point"
    local directions="down first last next prev root up"
    local opt_color_args="always auto never"
    local opt_return_to_args="here nearest-remaining stay"
    local opt_start_from_args="here root first-root"

    local common_opts="--debug -h --help -v --verbose --version"
    local add_opts="-o --onto= -R --as-root -y --yes"
    local advance_opts="-y --yes"
    local anno_opts="-b --branch="
    local delete_unmanaged_opts="-y --yes"
    local diff_opts="-s --stat"
    local discover_opts="-C --checked-out-since= -l --list-commits -r --roots= -y --yes"
    local fork_point_opts="--inferred --override-to= --override-to-inferred --override-to-parent --unset-override"
    local reapply_opts="-f --fork-point="
    local slide_out_opts="-d --down-fork-point= -M --merge -n --no-edit-merge --no-interactive-rebase"
    local status_opts="--color= -L --list-commits-with-hashes -l --list-commits"
    local traverse_opts="-F --fetch -l --list-commits -M --merge -n --no-edit-merge --no-interactive-rebase --return-to= --start-from= -w --whole -W -y --yes"
    local update_opts="-f --fork-point= -M --merge -n --no-edit-merge --no-interactive-rebase"

    case $cur in
        --branch=*|--onto=*) __gitcomp_nl "$(git machete list managed 2>/dev/null)" "" "${cur##--*=}" ;;
        --checked-out-since=*) __gitcomp "" ;;
        --color=*) __gitcomp "$opt_color_args" "" "${cur##--color=}" ;;
        --down-fork-point=*|--fork-point=*|--override-to=*) __gitcomp "$(__git_refs)" "" "${cur##--*=}" ;;
        --return-to=*) __gitcomp "$opt_return_to_args" "" "${cur##--return-to=}" ;;
        --roots=*) __gitcomp "$(__git_heads)" "" "${cur##--roots=}" ;;
        --start-from=*) __gitcomp "$opt_start_from_args" "" "${cur##--start-from=}" ;;
        -*)
            case ${COMP_WORDS[2]} in
                add) __gitcomp "$common_opts $add_opts" ;;
                advance) __gitcomp "$common_opts $advance_opts" ;;
                anno) __gitcomp "$common_opts $anno_opts" ;;
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
                local prev=${COMP_WORDS[COMP_CWORD-1]}
                case $prev in
                    -b|--branch|-o|--onto) __gitcomp_nl "$(git machete list managed 2>/dev/null)" ;;
                    -C|--checked-out-since) __gitcomp "" ;;
                    --color) __gitcomp "$opt_color_args" ;;
                    -d|--down-fork-point|-f|--fork-point|--override-to) __gitcomp "$(__git_refs)" ;;
                    # TODO (GH issue #25): We don't complete --help since it's going to be captured by git anyway
                    # (and results in redirection to yet non-existent man for `git-machete`).
                    -h) __gitcomp "$help_topics" ;;
                    --return-to) __gitcomp "$opt_return_to_args" ;;
                    # TODO complete the comma-separated list of roots
                    -r|--roots) __gitcomp "$(__git_heads)" ;;
                    --start-from) __gitcomp "$opt_start_from_args" ;;
                    --unset-override) __gitcomp_nl "$(git machete list with-overridden-fork-point 2>/dev/null)" ;;
                    *)
                        case ${COMP_WORDS[2]} in
                            add) __gitcomp_nl "$(git machete list addable 2>/dev/null)" ;;
                            d|diff|fork-point|is-managed|l|log) __gitcomp "$(__git_heads)" ;;
                            g|go) __gitcomp "$directions" ;;
                            help) __gitcomp "$help_topics" ;;
                            list)
                                if [[ $COMP_CWORD -eq 3 ]]; then
                                    __gitcomp "$categories"
                                elif [[ $COMP_CWORD -eq 4 && $prev == slidable-after ]]; then
                                    __gitcomp_nl "$(git machete list slidable 2>/dev/null)"
                                fi ;;
                            show) __gitcomp "current $directions" ;;
                            slide-out)
                                if [[ $COMP_CWORD -eq 3 ]]; then
                                    __gitcomp_nl "$(git machete list slidable 2>/dev/null)"
                                else
                                    __gitcomp_nl "$(git machete list slidable-after "$prev" 2>/dev/null)"
                                fi ;;
                            *) COMPREPLY=('') ;; # not perfect (kinda-completes an empty string), but at least local paths aren't completed by default
                        esac ;;
                esac
            fi
    esac
}
