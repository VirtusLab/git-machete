#!/usr/bin/env bash

set -e -o pipefail -u -x

milestone_title=v$(cut -d\' -f2 git_machete/__init__.py)

milestones_json_array=$(gh api repos/VirtusLab/git-machete/milestones)
milestone=$(echo "$milestones_json_array" | jq -c --arg TITLE "$milestone_title" '.[] | select(.title == $TITLE)')

number=$(echo "$milestone" | jq '.number')
# open issues and PRs are counted together in the same field
open_issue_count=$(echo "$milestone" | jq '.open_issues')

if [[ $open_issue_count = 0 ]]; then
  gh api --method PATCH "repos/VirtusLab/git-machete/milestones/$number" -f state=closed
fi
