#!/usr/bin/env bash

# Check if any of the given options appear in the current command line words.
# Usage: _git_machete_seen_opt --opt1 -o --opt2 ...
_git_machete_seen_opt() {
  local opt
  for opt in "$@"; do
    local word
    for word in "${COMP_WORDS[@]}"; do
      # Handle options with = (e.g. --onto= matches --onto=* and --onto)
      if [[ "$opt" == *"=" ]]; then
        if [[ "$word" == "${opt%=}" || "$word" == "${opt}"* ]]; then
          return 0
        fi
      else
        if [[ "$word" == "$opt" ]]; then
          return 0
        fi
      fi
    done
  done
  return 1
}

_git_machete() {
  local cmds="add advance anno completion delete-unmanaged diff discover edit file fork-point github gitlab go help is-managed list log reapply show slide-out squash status traverse update version"
  local help_topics="$cmds config format hooks"

  local categories="addable childless managed slidable slidable-after unmanaged with-overridden-fork-point"
  local directions="down first last next prev root up"
  local github_subcommands="anno-prs checkout-prs create-pr restack-pr retarget-pr update-pr-descriptions"
  local gitlab_subcommands="anno-mrs checkout-mrs create-mr restack-mr retarget-mr update-mr-descriptions"
  local locations="current $directions"
  local opt_color_args="always auto never"
  local opt_return_to_args="HERE NEAREST-REMAINING STAY"
  local opt_start_from_args="HERE ROOT FIRST-ROOT"
  local shells="bash fish zsh"

  local common_opts="--debug -h --help -v --verbose"
  local add_opts="-f --as-first-child -o --onto= -R --as-root -y --yes"
  local advance_opts="-y --yes"
  local anno_opts="-b --branch= -H --sync-github-prs -L --sync-gitlab-mrs"
  local delete_unmanaged_opts="-y --yes"
  local diff_opts="-s --stat"
  local discover_opts="-C --checked-out-since= -l --list-commits -r --roots= -y --yes"
  local fork_point_opts="--inferred --override-to= --override-to-inferred --override-to-parent --unset-override"
  local githublab_anno_opts="--with-urls"
  local githublab_create_opts="--draft --title= -U --update-related-descriptions -y --yes"
  local githublab_checkout_opts="--all --by= --mine"
  local githublab_restack_opts="-U --update-related-descriptions"
  local githublab_retarget_opts="-b --branch= --ignore-if-missing -U --update-related-descriptions"
  local githublab_update_descriptions_opts="--all --by= --mine --related"
  local reapply_opts="-f --fork-point="
  local slide_out_opts="-d --down-fork-point= --delete -M --merge -n --no-edit-merge --no-interactive-rebase --no-rebase --removed-from-remote"
  local squash_opts="-f --fork-point="
  local status_opts="--color= -L --list-commits-with-hashes -l --list-commits --no-detect-squash-merges"
  local traverse_opts="-F --fetch -H --sync-github-prs -L --sync-gitlab-mrs -l --list-commits -M --merge -n --no-detect-squash-merges --no-edit-merge --no-interactive-rebase --no-push --no-push-untracked --push --push-untracked --return-to= --start-from= --stop-after= -w --whole -W -y --yes"
  local update_opts="-f --fork-point= -M --merge -n --no-edit-merge --no-interactive-rebase"

  cur=${COMP_WORDS[$COMP_CWORD]}
  case $cur in
    --branch=*|--onto=*) __gitcomp_nl "$(git machete list managed 2>/dev/null)" "" "${cur##--*=}" ;;
    --by=*|--checked-out-since=*) COMPREPLY=('');;
    --color=*) __gitcomp "$opt_color_args" "" "${cur##--color=}" ;;
    --down-fork-point=*|--fork-point=*|--override-to=*) __gitcomp "$(__git_refs)" "" "${cur##--*=}" ;;
    --return-to=*) __gitcomp "$opt_return_to_args" "" "${cur##--return-to=}" ;;
    --roots=*) __gitcomp "$(__git_heads)" "" "${cur##--roots=}" ;;
    --start-from=*) __gitcomp "$opt_start_from_args $(__git_heads)" "" "${cur##--start-from=}" ;;
    --stop-after=*) __gitcomp "$(__git_heads)" "" "${cur##--stop-after=}" ;;
    -*)
      case ${COMP_WORDS[2]} in
        add)
          local filtered_add_opts="$add_opts"
          if _git_machete_seen_opt -R --as-root; then
            filtered_add_opts=$(echo "$filtered_add_opts" | tr ' ' '\n' | grep -v '^\(-f\|--as-first-child\|-o\|--onto=\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt -o --onto= || _git_machete_seen_opt -f --as-first-child; then
            filtered_add_opts=$(echo "$filtered_add_opts" | tr ' ' '\n' | grep -v '^\(-R\|--as-root\)$' | tr '\n' ' ')
          fi
          __gitcomp "$common_opts $filtered_add_opts"
          ;;
        advance) __gitcomp "$common_opts $advance_opts" ;;
        anno)
          local filtered_anno_opts="$anno_opts"
          if _git_machete_seen_opt -H --sync-github-prs; then
            filtered_anno_opts=$(echo "$filtered_anno_opts" | tr ' ' '\n' | grep -v '^\(-L\|--sync-gitlab-mrs\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt -L --sync-gitlab-mrs; then
            filtered_anno_opts=$(echo "$filtered_anno_opts" | tr ' ' '\n' | grep -v '^\(-H\|--sync-github-prs\)$' | tr '\n' ' ')
          fi
          __gitcomp "$common_opts $filtered_anno_opts"
          ;;
        d|diff) __gitcomp "$common_opts $diff_opts" ;;
        delete-unmanaged) __gitcomp "$common_opts $delete_unmanaged_opts" ;;
        discover) __gitcomp "$common_opts $discover_opts" ;;
        fork-point)
          local filtered_fork_point_opts="$fork_point_opts"
          # Form 1: --inferred
          if _git_machete_seen_opt --inferred; then
            filtered_fork_point_opts=$(echo "$filtered_fork_point_opts" | tr ' ' '\n' | grep -v '^\(--override-to=\|--override-to-inferred\|--override-to-parent\|--unset-override\)$' | tr '\n' ' ')
          fi
          # Form 2: --override-to/--override-to-inferred/--override-to-parent
          if _git_machete_seen_opt --override-to= --override-to-inferred --override-to-parent; then
            filtered_fork_point_opts=$(echo "$filtered_fork_point_opts" | tr ' ' '\n' | grep -v '^\(--inferred\|--unset-override\)$' | tr '\n' ' ')
          fi
          # Form 3: --unset-override
          if _git_machete_seen_opt --unset-override; then
            filtered_fork_point_opts=$(echo "$filtered_fork_point_opts" | tr ' ' '\n' | grep -v '^\(--inferred\|--override-to=\|--override-to-inferred\|--override-to-parent\)$' | tr '\n' ' ')
          fi
          __gitcomp "$common_opts $filtered_fork_point_opts"
          ;;
        github)
          case ${COMP_WORDS[3]} in
            "anno-prs") __gitcomp "$common_opts $githublab_anno_opts" ;;
            "create-pr") __gitcomp "$common_opts $githublab_create_opts" ;;
            "checkout-prs") __gitcomp "$common_opts $githublab_checkout_opts" ;;
            "restack-pr") __gitcomp "$common_opts $githublab_restack_opts" ;;
            "retarget-pr") __gitcomp "$common_opts $githublab_retarget_opts" ;;
            "update-pr-descriptions") __gitcomp "$common_opts $githublab_update_descriptions_opts" ;;
            *) __gitcomp "$common_opts" ;;
          esac ;;
        gitlab)
          case ${COMP_WORDS[3]} in
            "anno-mrs") __gitcomp "$common_opts $githublab_anno_opts" ;;
            "create-mr") __gitcomp "$common_opts $githublab_create_opts" ;;
            "checkout-mrs") __gitcomp "$common_opts $githublab_checkout_opts" ;;
            "restack-mr") __gitcomp "$common_opts $githublab_restack_opts" ;;
            "retarget-mr") __gitcomp "$common_opts $githublab_retarget_opts" ;;
            "update-mr-descriptions") __gitcomp "$common_opts $githublab_update_descriptions_opts" ;;
            *) __gitcomp "$common_opts" ;;
          esac ;;
        reapply) __gitcomp "$common_opts $reapply_opts" ;;
        slide-out)
          local filtered_slide_out_opts="$slide_out_opts"
          if _git_machete_seen_opt --removed-from-remote; then
            filtered_slide_out_opts=$(echo "$filtered_slide_out_opts" | tr ' ' '\n' | grep -v '^\(-d\|--down-fork-point=\|-M\|--merge\|-n\|--no-edit-merge\|--no-interactive-rebase\|--no-rebase\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt -M --merge; then
            filtered_slide_out_opts=$(echo "$filtered_slide_out_opts" | tr ' ' '\n' | grep -v '^\(-d\|--down-fork-point=\|--no-interactive-rebase\|--removed-from-remote\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt -d --down-fork-point=; then
            filtered_slide_out_opts=$(echo "$filtered_slide_out_opts" | tr ' ' '\n' | grep -v '^\(-M\|--merge\|--no-rebase\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt -n; then
            filtered_slide_out_opts=$(echo "$filtered_slide_out_opts" | tr ' ' '\n' | grep -v '^\(--no-edit-merge\|--no-interactive-rebase\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt --no-edit-merge; then
            filtered_slide_out_opts=$(echo "$filtered_slide_out_opts" | tr ' ' '\n' | grep -v '^\(-n\|--no-interactive-rebase\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt --no-interactive-rebase; then
            filtered_slide_out_opts=$(echo "$filtered_slide_out_opts" | tr ' ' '\n' | grep -v '^\(-n\|--no-edit-merge\|-M\|--merge\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt --no-rebase; then
            filtered_slide_out_opts=$(echo "$filtered_slide_out_opts" | tr ' ' '\n' | grep -v '^\(-d\|--down-fork-point=\|-M\|--merge\|--no-interactive-rebase\|--no-edit-merge\)$' | tr '\n' ' ')
          fi
          __gitcomp "$common_opts $filtered_slide_out_opts"
          ;;
        squash) __gitcomp "$common_opts $squash_opts" ;;
        s|status) __gitcomp "$common_opts $status_opts" ;;
        t|traverse)
          local filtered_traverse_opts="$traverse_opts"
          if _git_machete_seen_opt -W; then
            filtered_traverse_opts=$(echo "$filtered_traverse_opts" | tr ' ' '\n' | grep -v '^\(-F\|--fetch\|-l\|--list-commits\|-w\|--whole\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt -H --sync-github-prs; then
            filtered_traverse_opts=$(echo "$filtered_traverse_opts" | tr ' ' '\n' | grep -v '^\(-L\|--sync-gitlab-mrs\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt -L --sync-gitlab-mrs; then
            filtered_traverse_opts=$(echo "$filtered_traverse_opts" | tr ' ' '\n' | grep -v '^\(-H\|--sync-github-prs\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt -M --merge; then
            filtered_traverse_opts=$(echo "$filtered_traverse_opts" | tr ' ' '\n' | grep -v '^\(--no-interactive-rebase\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt -n; then
            filtered_traverse_opts=$(echo "$filtered_traverse_opts" | tr ' ' '\n' | grep -v '^\(--no-edit-merge\|--no-interactive-rebase\|-y\|--yes\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt --no-edit-merge; then
            filtered_traverse_opts=$(echo "$filtered_traverse_opts" | tr ' ' '\n' | grep -v '^\(-n\|--no-interactive-rebase\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt --no-interactive-rebase; then
            filtered_traverse_opts=$(echo "$filtered_traverse_opts" | tr ' ' '\n' | grep -v '^\(-n\|--no-edit-merge\|-M\|--merge\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt --no-push; then
            filtered_traverse_opts=$(echo "$filtered_traverse_opts" | tr ' ' '\n' | grep -v '^\(--push\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt --push; then
            filtered_traverse_opts=$(echo "$filtered_traverse_opts" | tr ' ' '\n' | grep -v '^\(--no-push\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt --no-push-untracked; then
            filtered_traverse_opts=$(echo "$filtered_traverse_opts" | tr ' ' '\n' | grep -v '^\(--push-untracked\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt --push-untracked; then
            filtered_traverse_opts=$(echo "$filtered_traverse_opts" | tr ' ' '\n' | grep -v '^\(--no-push-untracked\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt -w --whole; then
            filtered_traverse_opts=$(echo "$filtered_traverse_opts" | tr ' ' '\n' | grep -v '^\(-W\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt -y --yes; then
            filtered_traverse_opts=$(echo "$filtered_traverse_opts" | tr ' ' '\n' | grep -v '^\(-n\)$' | tr '\n' ' ')
          fi
          __gitcomp "$common_opts $filtered_traverse_opts"
          ;;
        update)
          local filtered_update_opts="$update_opts"
          if _git_machete_seen_opt -M --merge; then
            filtered_update_opts=$(echo "$filtered_update_opts" | tr ' ' '\n' | grep -v '^\(-f\|--fork-point=\|--no-interactive-rebase\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt -f --fork-point=; then
            filtered_update_opts=$(echo "$filtered_update_opts" | tr ' ' '\n' | grep -v '^\(-M\|--merge\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt -n; then
            filtered_update_opts=$(echo "$filtered_update_opts" | tr ' ' '\n' | grep -v '^\(--no-edit-merge\|--no-interactive-rebase\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt --no-edit-merge; then
            filtered_update_opts=$(echo "$filtered_update_opts" | tr ' ' '\n' | grep -v '^\(-n\|--no-interactive-rebase\)$' | tr '\n' ' ')
          fi
          if _git_machete_seen_opt --no-interactive-rebase; then
            filtered_update_opts=$(echo "$filtered_update_opts" | tr ' ' '\n' | grep -v '^\(-n\|--no-edit-merge\|-M\|--merge\)$' | tr '\n' ' ')
          fi
          __gitcomp "$common_opts $filtered_update_opts"
          ;;
        *)
          if [[ $COMP_CWORD -eq 2 ]]; then
            __gitcomp "$common_opts --version"
          else
            __gitcomp "$common_opts"
          fi ;;
      esac ;;
    *)
      if [[ $COMP_CWORD -eq 2 ]]; then
        if [[ $cmds =~ ^$cur ]] || [[ $cmds =~ ( $cur) ]]; then
          __gitcomp "$cmds"
        else
          COMPREPLY=('')
        fi
      else
        local prev=${COMP_WORDS[COMP_CWORD-1]}
        case $prev in
          -b|--branch|-o|--onto) __gitcomp_nl "$(git machete list managed 2>/dev/null)" ;;
          --by=*|-C|--checked-out-since=*) COMPREPLY=('');;
          --color) __gitcomp "$opt_color_args" ;;
          -d|--down-fork-point|-f|--fork-point|--override-to) __gitcomp "$(__git_refs)" ;;
          # TODO (#895): we don't complete --help since it's going to be captured by git anyway
          # and results in redirection to man for `git-machete`,
          # which is only properly installed by some package systems as for now (see PACKAGES.md).
          -h) __gitcomp "$help_topics" ;;
          --return-to) __gitcomp "$opt_return_to_args" ;;
          # TODO (#111): complete the comma-separated list of roots
          -r|--roots) __gitcomp "$(__git_heads)" ;;
          --start-from) __gitcomp "$opt_start_from_args $(__git_heads)" ;;
          --stop-after) __gitcomp "$(__git_heads)" ;;
          --unset-override) __gitcomp_nl "$(git machete list with-overridden-fork-point 2>/dev/null)" ;;
          *)
            case ${COMP_WORDS[2]} in
              add)
                __gitcomp_nl "$(git machete list addable 2>/dev/null)" ;;
              completion)
                __gitcomp "$shells" ;;
              d|diff|fork-point|is-managed|l|log)
                __gitcomp "$(__git_heads)" ;;
              g|go)
                if [[ $COMP_CWORD -eq 3 ]]; then
                  __gitcomp "$directions"
                else
                  COMPREPLY=('')
                fi ;;
              github)
                if [[ $COMP_CWORD -eq 3 ]]; then
                  __gitcomp "$github_subcommands"
                else
                  case ${COMP_WORDS[3]} in
                    "anno-prs") __gitcomp "$common_opts $githublab_anno_opts" ;;
                    "create-pr") __gitcomp "$common_opts $githublab_create_opts" ;;
                    "checkout-prs") __gitcomp "$common_opts $githublab_checkout_opts" ;;
                    "restack-pr") __gitcomp "$common_opts $githublab_restack_opts" ;;
                    "retarget-pr") __gitcomp "$common_opts $githublab_retarget_opts" ;;
                    "update-pr-descriptions") __gitcomp "$common_opts $githublab_update_descriptions_opts" ;;
                    *) COMPREPLY=('') ;;
                  esac
                fi ;;
              gitlab)
                if [[ $COMP_CWORD -eq 3 ]]; then
                  __gitcomp "$gitlab_subcommands"
                else
                  case ${COMP_WORDS[3]} in
                    "anno-mrs") __gitcomp "$common_opts $githublab_anno_opts" ;;
                    "create-mr") __gitcomp "$common_opts $githublab_create_opts" ;;
                    "checkout-mrs") __gitcomp "$common_opts $githublab_checkout_opts" ;;
                    "restack-mr") __gitcomp "$common_opts $githublab_restack_opts" ;;
                    "retarget-mr") __gitcomp "$common_opts $githublab_retarget_opts" ;;
                    "update-mr-descriptions") __gitcomp "$common_opts $githublab_update_descriptions_opts" ;;
                    *) COMPREPLY=('') ;;
                  esac
                fi ;;
              help)
                if [[ $COMP_CWORD -eq 3 ]]; then
                  __gitcomp "$help_topics"
                else
                  COMPREPLY=('')
                fi ;;
              list)
                if [[ $COMP_CWORD -eq 3 ]]; then
                  __gitcomp "$categories"
                elif [[ $COMP_CWORD -eq 4 && $prev == "slidable-after" ]]; then
                  __gitcomp_nl "$(git machete list slidable 2>/dev/null)"
                else
                  COMPREPLY=('')
                fi ;;
              show)
                if [[ $COMP_CWORD -eq 3 ]]; then
                  __gitcomp "$locations"
                elif [[ $COMP_CWORD -eq 4 && $prev != "current" ]]; then
                  __gitcomp_nl "$(git machete list managed 2>/dev/null)"
                else
                  COMPREPLY=('')
                fi ;;
              slide-out)
                if [[ $COMP_CWORD -eq 3 ]]; then
                  __gitcomp_nl "$(git machete list slidable 2>/dev/null)"
                else
                  __gitcomp_nl "$(git machete list slidable-after "$prev" 2>/dev/null)"
                fi ;;
                # Not perfect (kinda-completes an empty string), but at least local file paths aren't completed by default
              *) COMPREPLY=('') ;;
            esac ;;
        esac
      fi
  esac
}
