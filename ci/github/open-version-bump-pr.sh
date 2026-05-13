#!/usr/bin/env bash

set -e -o pipefail -u -x

# Opens a routine patch-version-bump PR (`<major>.<minor>.<patch>++`) atop the
# just-released `master`.

current_version=$(cut -d\' -f2 git_machete/__init__.py)
IFS=. read -r major minor patch <<< "$current_version"
new_version="${major}.${minor}.$((patch + 1))"
branch="bump-version-to-v${new_version}"

# Idempotent: bail out if the bump PR for this version already exists
# (e.g. the CI stage is being re-run after a transient failure downstream).
if [[ -n $(gh pr list --head "$branch" --state all --json number --jq '.[].number' 2>/dev/null || true) ]]; then
  echo "PR for branch '$branch' already exists; nothing to do."
  exit 0
fi

sed -i "s/__version__ = '$current_version'/__version__ = '$new_version'/" git_machete/__init__.py

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

# Same git identity used by the sister `git-machete-intellij-plugin` repo
# for CI-authored bot commits.
git config user.name "Git Machete Bot"
git config user.email "gitmachete@virtuslab.com"

# Use `GITHUB_TOKEN` for `git push` (the same env var that `gh` already
# consumes in master jobs); we don't depend on the checkout deploy key
# having write access.
git remote set-url origin "https://${GITHUB_TOKEN}@github.com/VirtusLab/git-machete.git"

git checkout -b "$branch"
git add git_machete/__init__.py RELEASE_NOTES.md
git commit -m "Bump version to v${new_version}"
git push origin "$branch"

gh pr create \
  --title "Bump version to v${new_version}" \
  --body "Routine patch-version bump opened automatically after \`v${current_version}\` was released." \
  --base master \
  --head "$branch"
