#!/usr/bin/env bash

set -e -o pipefail -u -x

# Opens a routine patch-version-bump PR (`<major>.<minor>.<patch>++`) atop the
# mainline `develop` branch (where the next release is being prepared) rather
# than `master` - so the bump rides along with whatever else is already queued
# for the next release.
#
# Runs as part of the `master`-only release job, so the workspace starts out
# on `master` at the just-released tag.

# Captured up-front from master's `__init__.py` (= the version that was just
# released); used only in the PR body.
released_version=$(cut -d\' -f2 git_machete/__init__.py)

# Same git identity used by the sister `git-machete-intellij-plugin` repo
# for CI-authored bot commits.
git config user.name "Git Machete Bot"
git config user.email "gitmachete@virtuslab.com"

# Use `GITHUB_TOKEN` for `git push` (the same env var that `gh` already
# consumes in master jobs); we don't depend on the checkout deploy key
# having write access.
git remote set-url origin "https://${GITHUB_TOKEN}@github.com/VirtusLab/git-machete.git"

# Read the version off `develop` (which may already be ahead of the just-released
# `master` - e.g. a minor-bump landed there meanwhile) so the new patch number
# is computed relative to what develop will actually compare against.
git fetch origin develop
develop_version=$(git show origin/develop:git_machete/__init__.py | cut -d\' -f2)
IFS=. read -r major minor patch <<< "$develop_version"
new_version="${major}.${minor}.$((patch + 1))"
branch="bump-version-to-v${new_version}"

# Idempotent: bail out if the bump PR for this version already exists
# (e.g. the CI stage is being re-run after a transient failure downstream).
if [[ -n $(gh pr list --head "$branch" --state all --json number --jq '.[].number' 2>/dev/null || true) ]]; then
  echo "PR for branch '$branch' already exists; nothing to do."
  exit 0
fi

git checkout -b "$branch" origin/develop

sed -i "s/__version__ = '$develop_version'/__version__ = '$new_version'/" git_machete/__init__.py

# Insert a new "## New in git-machete <new>" header (plus a blank line below it)
# above the previous latest-version section. `enforce-release-notes-up-to-date.sh`
# reads line 3 of `RELEASE_NOTES.md` to verify the version matches `__init__.py`,
# so the new header must land on line 3.
{ head -n 2 RELEASE_NOTES.md
  echo "## New in git-machete ${new_version}"
  echo
  tail -n +3 RELEASE_NOTES.md
} > RELEASE_NOTES.md.tmp
mv RELEASE_NOTES.md.tmp RELEASE_NOTES.md

# Regenerate the Sphinx-built man page so its embedded version string matches
# the bumped `__init__.py`; otherwise `tox -e sphinx-man-check` (run as part
# of regular CI on the bump PR) would fail. `tox` isn't pre-installed in the
# release executor - other CircleCI jobs `pip3 install tox` for the same reason.
pip3 install tox
tox -e sphinx-man

git add git_machete/__init__.py RELEASE_NOTES.md docs/man/git-machete.1
git commit -m "Bump version to v${new_version}"
git push origin "$branch"

gh pr create \
  --title "Bump version to v${new_version}" \
  --body "Routine patch-version bump opened automatically after \`v${released_version}\` was released." \
  --base develop \
  --head "$branch"
