#!/usr/bin/env bash

_git_machete() {
    cmds="add anno d delete-unmanaged diff discover e edit file fork-point g go help l list log reapply show slide-out s status traverse update"
    help_topics="$cmds format hooks"
    categories="managed slidable slidable-after unmanaged"
    color_modes="always auto never"
    directions="down first last next prev root up"

    common_opts="--debug -h --help -v --verbose --version"
    add_opts="-o --onto="
    diff_opts="-s --stat"
    discover_opts="-C --checked-out-since= -l --list-commits -r --roots="
    reapply_opts="-f --fork-point="
    slide_out_opts="-d --down-fork-point="
    status_opts="-l --list-commits --color="
    traverse_opts="-l --list-commits"
    update_opts="-f --fork-point="

    case "$cur" in
        --checked-out-since=*) __gitcomp "" ;;
        --down-fork-point=*|--fork-point=*) __gitcomp "$(__git_refs)" "" "${cur##--*=}" ;;
        --onto=*) __gitcomp_nl "$(git machete list managed)" "" "${cur##--onto=}" ;;
        --roots=*) __gitcomp "$(__git_heads)" "" "${cur##--roots=}" ;;
        --color=*) __gitcomp "$color_modes" "" "${cur##--color=}" ;;
        -*)
            case "${COMP_WORDS[2]}" in
                add) __gitcomp "$common_opts $add_opts" ;;
                d|diff) __gitcomp "$common_opts $diff_opts" ;;
                discover) __gitcomp "$common_opts $discover_opts" ;;
                reapply) __gitcomp "$common_opts $reapply_opts" ;;
                slide-out) __gitcomp "$common_opts $slide_out_opts" ;;
                s|status) __gitcomp "$common_opts $status_opts" ;;
                traverse) __gitcomp "$common_opts $traverse_opts" ;;
                update) __gitcomp "$common_opts $update_opts" ;;
                *) __gitcomp "$common_opts" ;;
            esac ;;
         *)
             if [[ "$COMP_CWORD" -eq 2 ]]; then
                __gitcomp "$cmds"
             else
                prev="${COMP_WORDS[COMP_CWORD-1]}"
                case "$prev" in
                    -C|--checked-out-since) __gitcomp "" ;;
                    -d|--down-fork-point|-f|--fork-point) __gitcomp "$(__git_refs)" ;;
                    # TODO #25: We don't complete --help since it's going to be captured by git anyway
                    # (and results in redirection to yet non-existent man for `git-machete`).
                    -h) __gitcomp "$help_topics" ;;
                    -o|--onto) __gitcomp_nl "$(git machete list managed)" ;;
                    # TODO complete the comma-separated list of roots
                    -r|--roots) __gitcomp "$(__git_heads)" ;;
                    *)
                        case "${COMP_WORDS[2]}" in
                            add) __gitcomp_nl "$(git machete list unmanaged)" ;;
                            d|diff|fork-point|l|log) __gitcomp "$(__git_heads)" ;;
                            g|go|show) __gitcomp "$directions" ;;
                            help) __gitcomp "$help_topics" ;;
                            list)
                                if [[ "$COMP_CWORD" -eq 3 ]]; then
                                    __gitcomp "$categories"
                                elif [[ "$COMP_CWORD" -eq 4 ]] && [[ "$prev" == "slidable-after" ]]; then
                                    __gitcomp_nl "$(git machete list slidable)"
                                fi ;;
                            slide-out)
                                if [[ "$COMP_CWORD" -eq 3 ]]; then
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
