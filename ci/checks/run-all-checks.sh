#!/usr/bin/env bash

set -e

# We don't want `less` to open for `git grep` results.
export GIT_PAGER=cat

function _() {
  script=$1
  echo "> $script" >&2
  if ! "./ci/checks/$script.sh"; then
    failed="$failed, $script"
  fi
}

_ enforce-bumped-version
_ enforce-consistent-style-for-fork-point
_ enforce-consistent-style-for-github
_ enforce-consistent-style-for-gitlab
_ enforce-correct-shebangs
_ enforce-indent-two-spaces-outside-python
_ enforce-issue-number-for-todos
if [[ $CI ]] || command -v remark; then
  _ enforce-links-correct
else
  echo 'Warning: remark CLI not installed, link check will be skipped. Use `npm install remark-cli remark-validate-links`'
fi
_ enforce-mocking-only-whitelisted-methods
_ enforce-newline-at-eof
_ enforce-release-notes-up-to-date
_ enforce-shell-scripts-pass-shellcheck
_ enforce-tox-testenvs-all-have-deps
_ enforce-yq-check-for-each-y-yes-yq-check
_ prohibit-a-mr
_ prohibit-all-caps-not-in-rst
_ prohibit-bash-usages-from-python
_ prohibit-current-date-in-tests
_ prohibit-deploy-step-in-circleci
_ prohibit-double-backticks-in-python
_ prohibit-exempli-gratia-in-rst
_ prohibit-fish-completion-repetition-checks-for-long-options
_ prohibit-fork-point-in-git-context
_ prohibit-github-in-gitlab-files
_ prohibit-github-mr-or-gitlab-pr
_ prohibit-gitlab-in-github-files
_ prohibit-grey
_ prohibit-id-est-in-rst
_ prohibit-markdown-links-in-rst
_ prohibit-mrs-in-github-files
_ prohibit-prs-in-gitlab-files
_ prohibit-single-backtick-in-rst
_ prohibit-split-backslash-n
_ prohibit-strings-split-without-delimiter
_ prohibit-strings-with-backslash-continuation
_ prohibit-strings-with-useless-interpolations
_ prohibit-tab-character
_ prohibit-trailing-whitespace

if [[ $failed ]]; then
  echo
  echo "ERROR: ${failed#, } failed" >&2
  exit 1
fi
