set -e -o pipefail -u

self_dir=$(cd "$(dirname "$0")" &>/dev/null; pwd -P)
source "$self_dir"/utils.sh

if git grep -wqe Github -- README.md RELEASE_NOTES.md CONTRIBUTING.md git_machete docs completion; then
  die "Please use 'GitHub' instead of 'Github'."
fi
