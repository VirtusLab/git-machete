#!/usr/bin/env bash

set -e -o pipefail -u -x

HOMEBREW_VERSION=4.2.11

export HOMEBREW_NO_AUTO_UPDATE=1

NONINTERACTIVE=1 bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
# https://stackoverflow.com/questions/54912857/how-do-i-install-old-version-of-homebrew-itself-not-the-formula
(cd /home/linuxbrew/.linuxbrew/Homebrew; git checkout $HOMEBREW_VERSION)
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
brew --version

if [[ ${1-} == "--dry-run" || ${CIRCLE_BRANCH-} != "master" ]]; then
  do_push=false
  pypi_host=test.pypi.org
else
  do_push=true
  pypi_host=pypi.org
fi

version=$(cut -d\' -f2 git_machete/__init__.py)
# Do not use https://*files.pythonhosted.org/... URLs, see https://github.com/orgs/Homebrew/discussions/5193
url="https://$pypi_host/packages/source/g/git-machete/git-machete-$version.tar.gz"
sha256=$(
  curl -s https://$pypi_host/pypi/git-machete/"$version"/json \
  | jq --raw-output '.urls | map(select(.packagetype == "sdist")) | .[0].digests.sha256')

# We need to run `brew tap homebrew/core` manually because:
# 1. the formula files need to be present at .../.linuxbrew/Homebrew/Library/Taps/... -
#    otherwise, `brew bump-formula-pr` will fail due to missing formula AND
# 2. since Homebrew 4.0.0 it is no longer done by default when installing `brew`; see https://brew.sh/2023/02/16/homebrew-4.0.0/
# Also, we can't use `--shallow` here (even though it'd save us ~3 minutes), this option is no longer supported (see https://stackoverflow.com/a/65243764).
brew tap --force homebrew/core
brew developer on
brew config

echo "Bump Homebrew formula"
flags=(--no-browse --verbose --url "$url" --sha256 "$sha256")
if [[ $do_push == true ]]; then
  # Relying on HOMEBREW_GITHUB_API_TOKEN, provided by the CI
  # See https://docs.brew.sh/Manpage -> Ctrl+F HOMEBREW_GITHUB_API_TOKEN

  git config --global user.email "gitmachete@virtuslab.com"
  git config --global user.name "Git Machete Bot"

  # `--force` ignores the existence of open PRs for the same formula.
  # It is useful for the rare cases where a develop/master build runs while a PR for the previously released version is still pending.
  # See https://app.circleci.com/pipelines/github/VirtusLab/git-machete/3140/workflows/6ee0916d-fc11-49b2-b29a-5bbc95cb25c4/jobs/16418:
  #   Error: These open pull requests may be duplicates:
  #   git-machete 3.15.1 https://github.com/Homebrew/homebrew-core/pull/123123
  #   Duplicate PRs should not be opened. Use --force to override this error.
  brew bump-formula-pr --force      "${flags[@]}" git-machete
else
  echo "Refraining from push since it's a dry run"
  brew bump-formula-pr --write-only "${flags[@]}" git-machete

  # homebrew-core has been fetched by `brew tap` above
  tap_repo=/home/linuxbrew/.linuxbrew/Homebrew/Library/Taps/homebrew/homebrew-core
  (cd $tap_repo; GIT_PAGER="cat" git diff)
  brew install --build-from-source --formula $tap_repo/Formula/g/git-machete.rb

  if [[ "$version" != "$(git machete version | cut -d' ' -f3)" ]]; then
    echo "Something went wrong during brew installation: installed version does not match version from formula."
    echo "Formula version: $version, installed version: $(git machete version | cut -d' ' -f3)"
    exit 1
  fi
  if ! git machete --help | grep 'GIT-MACHETE(1)'; then
    echo "man page has not been installed, aborting"
    exit 1
  fi
  if ! git machete completion bash | grep '#!.*bash'; then
    echo "shell completion is not available in runtime, aborting"
    exit 1
  fi

  brew remove git-machete
fi
