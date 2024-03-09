#!/usr/bin/env bash

set -e -o pipefail -u -x

HOMEBREW_VERSION=4.2.11

export HOMEBREW_NO_AUTO_UPDATE=1

NONINTERACTIVE=1 bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
# https://stackoverflow.com/questions/54912857/how-do-i-install-old-version-of-homebrew-itself-not-the-formula
(cd /home/linuxbrew/.linuxbrew/Homebrew; git checkout $HOMEBREW_VERSION)
# The two lines below are added to avoid ->  Warning: /home/linuxbrew/.linuxbrew/bin is not in your PATH
(echo; echo 'eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"') >> /home/circleci/.bash_profile
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
url="https://$pypi_host/packages/source/g/git-machete/git-machete-$version.tar.gz"
sha256=$(
  curl -s https://$pypi_host/pypi/git-machete/"$version"/json \
  | jq --raw-output '.urls | map(select(.packagetype == "sdist")) | .[0].digests.sha256')

echo "Bump Homebrew formula"
brew developer on
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
  brew bump-formula-pr --force --no-browse --verbose --url "$url" --sha256 "$sha256" git-machete
else
  echo "Refraining from push since it's a dry run"
  git clone --depth=1 git@github.com:Homebrew/homebrew-core.git ~/homebrew-core
  formula_file=~/homebrew-core/Formula/g/git-machete.rb
  sed -i "s!^  url .*\$!  url \"$url\"!"          $formula_file
  sed -i "s!^  sha256 .*\$!  sha256 \"$sha256\"!" $formula_file

  brew config
  brew install --build-from-source --formula $formula_file

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
