#!/usr/bin/env bash

# We don't want `less` to open for `git grep` results.
export GIT_PAGER=cat

PATH=./ci/checks:$PATH

# `-x`, so that we have more clarity which check actually failed
# (rather than searching the right script by error message).
set -e -x

enforce-bumped-version.sh
enforce-consistent-style-for-fork-point.sh
enforce-consistent-style-for-github.sh
enforce-consistent-style-for-gitlab.sh
enforce-correct-shebangs.sh
enforce-indent-two-spaces-outside-python.sh
enforce-issue-number-for-todos.sh
if [[ $CI ]] || command -v remark; then
  enforce-links-correct.sh
else
  echo 'Warning: remark CLI not installed, link check will be skipped. Use `npm install remark-cli remark-validate-links`'
fi
enforce-mocking-only-whitelisted-methods.sh
enforce-newline-at-eof.sh
enforce-release-notes-up-to-date.sh
enforce-shell-scripts-pass-shellcheck.sh
enforce-tox-testenvs-all-have-deps.sh
enforce-yq-check-for-each-y-yes-yq-check.sh
prohibit-bash-usages-from-python.sh
prohibit-current-date-in-tests.sh
prohibit-deploy-step-in-circleci.sh
prohibit-double-backticks-in-python.sh
prohibit-exempli-gratia-in-rst.sh
prohibit-fork-point-in-git-context.sh
prohibit-github-in-gitlab-files.sh
prohibit-github-mr-or-gitlab-pr.sh
prohibit-gitlab-in-github-files.sh
prohibit-id-est-in-rst.sh
prohibit-markdown-links-in-rst.sh
prohibit-mrs-in-github-files.sh
prohibit-prs-in-gitlab-files.sh
prohibit-single-backtick-in-rst.sh
prohibit-split-backslash-n.sh
prohibit-strings-split-without-delimiter.sh
prohibit-strings-with-backslash-continuation.sh
prohibit-strings-with-useless-interpolations.sh
prohibit-tab-character.sh
prohibit-trailing-whitespace.sh
