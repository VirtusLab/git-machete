#!/usr/bin/env bash

# We don't want `less` to open for `git grep` results.
export GIT_PAGER=cat

PATH=./ci/checks:$PATH

# `-x`, so that we have more clarity which check actually failed
# (rather than searching the right script by error message).
set -e -x

enforce-completion-scripts-correct.sh
enforce-consistent-style-for-fork-point.sh
enforce-consistent-style-for-github.sh
enforce-correct-shebangs.sh
enforce-indent-two-spaces-outside-python.sh
enforce-issue-number-for-todos.sh
if [[ $0 != *.git/hooks/pre-commit ]]; then
  # This one needs to connect to the linked websites and can potentially run long,
  # let's skip it when this script is executed as git pre-commit hook.
  enforce-links-correct.sh
fi
enforce-newline-at-eof.sh
enforce-release-notes-up-to-date.sh
enforce-shell-scripts-pass-shellcheck.sh
enforce-version-bumped.sh
prohibit-bash-usages-from-python.sh
prohibit-deploy-step-in-circleci.sh
prohibit-double-backticks-in-python.sh
prohibit-markdown-links-in-rst.sh
prohibit-single-backtick-in-rst.sh
prohibit-strings-split-without-delimiter.sh
prohibit-strings-with-backslash-continuation.sh
prohibit-tab-character.sh
prohibit-trailing-whitespace.sh
