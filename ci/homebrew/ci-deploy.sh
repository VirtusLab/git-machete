#!/usr/bin/env bash

set -e -o pipefail -u -x

/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" < /dev/null
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"

if [[ ${1-} == "--dry-run" || ${CIRCLE_BRANCH-} != "master" ]]; then
  do_push=false
  pypi_host=test.pypi.org
else
  do_push=true
  pypi_host=pypi.org
fi

version=$(python3 setup.py --version)
url="https://$pypi_host/packages/source/g/git-machete/git-machete-$version.tar.gz"
sha256=$(
  curl -s https://$pypi_host/pypi/git-machete/"$version"/json \
  | jq --raw-output '.urls | map(select(.packagetype == "sdist")) | .[0].digests.sha256')

git config --global user.email "gitmachete@virtuslab.com"
git config --global user.name "Git Machete Bot"

# Relying on HOMEBREW_GITHUB_API_TOKEN, provided by the CI
# See https://docs.brew.sh/Manpage -> Ctrl+F HOMEBREW_GITHUB_API_TOKEN
#brew install git-machete
echo "Bump Homebrew formula"
# `--force` ignores the existence of open PRs for the same formula.
# It is useful for the rare cases where a develop/master build runs while a PR for the previously released version is still pending.
# See https://app.circleci.com/pipelines/github/VirtusLab/git-machete/3140/workflows/6ee0916d-fc11-49b2-b29a-5bbc95cb25c4/jobs/16418:
#   Error: These open pull requests may be duplicates:
#   git-machete 3.15.1 https://github.com/Homebrew/homebrew-core/pull/123123
#   Duplicate PRs should not be opened. Use --force to override this error.
brew developer off
flags=(--no-browse --verbose --url "$url" --sha256 "$sha256")
if [[ $do_push == true ]]; then
  brew bump-formula-pr "${flags[@]}" git-machete
else
  echo "Refraining from push since it's a dry run"
#  brew bump-formula-pr --write-only "${flags[@]}" git-machete
  brew bump-formula-pr --dry-run "${flags[@]}" git-machete

  export HOMEBREW_NO_INSTALL_FROM_API=1
  brew config
  echo "Attempt to install the formula locally"
  attempts=5
  i=1
  while true; do
    if brew install --build-from-source --formula /home/linuxbrew/.linuxbrew/Homebrew/Library/Taps/homebrew/homebrew-core/Formula/git-machete.rb; then
      break
    elif (( i < attempts )); then
      echo "Retrying the installation..."
      i=$((i + 1))
      sleep 60
    else
      echo "Installing the formula locally did not succeed despite $attempts attempts"
      exit 1
    fi
  done

  if [[ "$version" != "$(git machete --version | cut -d' ' -f4)" ]]; then
    echo "Something went wrong during brew installation: installed version does not match version from formula."
    echo "Formula version: $version, installed version: $(git machete --version | cut -d' ' -f4)"
    exit 1
  fi
  brew remove git-machete
fi
