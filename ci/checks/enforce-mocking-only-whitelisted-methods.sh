#!/usr/bin/env bash

set -e -o pipefail -u

self_dir=$(cd "$(dirname "$0")" &>/dev/null; pwd -P)
source "$self_dir"/utils.sh
self_name=$(basename "$0")

whitelisted_methods="\
builtins.input
builtins.open
git_machete.client.MacheteClient.is_stdout_a_tty
git_machete.git_operations.GitContext.fetch_remote
git_machete.github.GitHubClient.MAX_PULLS_PER_PAGE_COUNT
git_machete.github.GitHubToken.for_domain
git_machete.github.RemoteAndOrganizationAndRepository.from_url
git_machete.utils._popen_cmd
git_machete.utils._run_cmd
git_machete.utils.find_executable
os.path.isfile
shutil.which
sys.argv
urllib.request.urlopen"
actual_methods=$(git grep -Pho "(?<=self\.patch_symbol\(mocker, ['\"]).*?(?=['\"])" | LC_COLLATE=C sort -u)

# `comm -13` to list lines only present in the second input (actual methods) and not in the first (whitelisted methods)
# `grep ''` to check if the output is non-empty (true if non-empty, false if empty)
if comm -13 <(echo "$whitelisted_methods") <(echo "$actual_methods") | grep ''; then
  echo
  error "The above properties/methods are mocked in at least one test method, but are NOT whitelisted in $self_name."
  die   "While it is possible to add new whitelisted properties/methods, consider redesigning the test(s) first."
fi
