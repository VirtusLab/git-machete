#!/usr/bin/env bash

set -e -o pipefail -u

self_name=$(basename "$0")

# Note that builtins.open should NOT be mocked as it can interfere with coverage.py,
# see https://github.com/coveragepy/coveragepy/issues/2083#issuecomment-3521840036
whitelisted_methods="\
builtins.input
git_machete.client.go_interactive.GoInteractiveMacheteClient._get_max_visible_branches
git_machete.code_hosting.OrganizationAndRepository.from_url
git_machete.git_operations.GitContext.fetch_remote
git_machete.github.GitHubClient.MAX_PULLS_PER_PAGE_COUNT
git_machete.github.GitHubToken.for_domain
git_machete.gitlab.GitLabClient.MAX_PULLS_PER_PAGE_COUNT
git_machete.gitlab.GitLabToken.for_domain
git_machete.utils._popen_cmd
git_machete.utils._run_cmd
git_machete.utils.find_executable
git_machete.utils.get_current_date
git_machete.utils.is_stdout_a_tty
git_machete.utils.slurp_file
os.path.isfile
shutil.which
sys.argv
termios.tcgetattr
termios.tcsetattr
tty.setraw
urllib.request.urlopen"
actual_methods=$(git grep -Pho "(?<=self\.patch_symbol\(mocker, ['\"]).*?(?=['\"])" | LC_COLLATE=C sort -u)

# `comm -13` to list lines only present in the second input (actual methods) and not in the first (whitelisted methods)
# `grep ''` to check if the output is non-empty (true if non-empty, false if empty)
if comm -13 <(echo "$whitelisted_methods") <(echo "$actual_methods") | grep ''; then
  echo
  echo "The above properties/methods are mocked in at least one test method, but are NOT whitelisted in $self_name."
  echo "While it is possible to add new whitelisted properties/methods, consider redesigning the test(s) first."
  exit 1
fi
