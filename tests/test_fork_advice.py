from typing import Optional

import pytest
from pytest_mock import MockerFixture

from tests import mockers_github, mockers_gitlab
from tests.base_test import BaseTest
from tests.cli_runner import assert_success, rewrite_branch_layout_file
from tests.git_repository import add_remote, commit, create_repo, create_repo_with_remote, new_branch, push, set_git_config_key
from tests.mockers_code_hosting import mock_from_url


class TestForkAdvice(BaseTest):

    @pytest.mark.parametrize('provider', ['github', 'gitlab'])
    @pytest.mark.parametrize('advice', [None, 'true', 'false'])
    def test_create_from_fork(self, mocker: MockerFixture, provider: str, advice: Optional[str]) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        if provider == 'github':
            self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mockers_github.mock_github_token_for_domain_none)
            self.patch_symbol(mocker, 'urllib.request.urlopen', mockers_github.mock_urlopen(mockers_github.MockGitHubAPIState.with_prs()))
            display, short, base_label, head_label, repository = 'GitHub', 'PR', 'base', 'head', 'repository'
        else:
            self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mockers_gitlab.mock_gitlab_token_for_domain_none)
            self.patch_symbol(mocker, 'urllib.request.urlopen', mockers_gitlab.mock_urlopen(mockers_gitlab.MockGitLabAPIState.with_mrs()))
            display, short, base_label, head_label, repository = 'GitLab', 'MR', 'target', 'source', 'project'
        article = 'a' if provider == 'github' else 'an'
        create_repo_with_remote()
        fork_path = create_repo('remote-1', bare=True, switch_dir_to_new_repo=False)
        add_remote('fork', fork_path)
        new_branch('master')
        commit()
        push(remote='fork', set_upstream=False)
        push(remote='origin')
        new_branch('feature')
        commit()
        push(remote='origin')
        rewrite_branch_layout_file('master\n\tfeature')
        set_git_config_key(f'machete.{provider}.baseRemote', 'fork')
        if advice is not None:
            set_git_config_key('advice.macheteCreateFromFork', advice)
        warning = f"""
        Warn: {base_label} branch master lives in example-org/example-repo-1 {repository},
        while {head_label} branch feature lives in example-org/example-repo {repository}.
        git-machete will now attempt to create {article} {short} in example-org/example-repo-1.

        Note that due to the limitations of {display}'s {short} model, it is not possible to cleanly create stacked {short}s from forks.
        For example, in a hypothetical chain some-other-branch -> feature -> master, {article} {short} from some-other-branch to feature
        could not be created in example-org/example-repo-1, since its {head_label} branch feature lives in example-org/example-repo.
        Generally, {short}s need to be created in whatever {repository} the {base_label} branch lives.
        """ if advice != 'false' else ''
        expected = warning + f"""
        Checking if {head_label} branch feature exists in origin remote... YES
        Checking if {base_label} branch master exists in fork remote... YES
        Creating {article} {short} from feature to master... OK, see www.{provider}.com
        """
        assert_success([provider, f'create-{short.lower()}'], expected)
