set -e -o pipefail -u

self_dir=$(cd "$(dirname "$0")" &>/dev/null; pwd -P)
source "$self_dir"/utils.sh

if git grep -wqe forkpoint -- README.md RELEASE_NOTES.md CONTRIBUTING.md git_machete docs completion; then
  die "Please use 'fork point' or 'fork_point' instead of 'forkpoint'."
fi
