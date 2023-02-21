import os

from .mockers import (GitRepositorySandbox, assert_command,
                      get_current_commit_hash, launch_command)


class TestForkPoint:

    def setup_method(self) -> None:

        self.repo_sandbox = GitRepositorySandbox()

        (
            self.repo_sandbox
            # Create the remote and sandbox repos, chdir into sandbox repo
            .new_repo(self.repo_sandbox.remote_path, "--bare")
            .new_repo(self.repo_sandbox.local_path)
            .execute(f"git remote add origin {self.repo_sandbox.remote_path}")
            .execute('git config user.email "tester@test.com"')
            .execute('git config user.name "Tester Test"')
        )

    def test_fork_point(self) -> None:
        """
        Verify behaviour of a 'git machete fork-point' command.
        """
        fixed_committer_and_author_date = 'Mon 20 Aug 2018 20:19:19 +0200'
        os.environ['GIT_COMMITTER_DATE'] = fixed_committer_and_author_date
        os.environ['GIT_AUTHOR_DATE'] = fixed_committer_and_author_date
        try:
            (
                self.repo_sandbox.new_branch("master")
                    .add_file_with_content_and_commit(message="master commit.")
                    .new_branch("develop")
                    .add_file_with_content_and_commit(file_content='develop content', message="develop commit.")
                    .new_branch("feature")
                    .commit('feature commit.')
            )
        finally:
            # Clean-up environment variables
            os.environ.pop('GIT_COMMITTER_DATE', None)
            os.environ.pop('GIT_AUTHOR_DATE', None)

        launch_command('discover', '-y')

        # Test `git machete fork-point` without providing the branch name
        # hash 67007ed30def3b9b658380b895a9f62b525286e0 corresponds to the commit on develop branch
        assert_command(["fork-point"], "67007ed30def3b9b658380b895a9f62b525286e0\n", strip_indentation=False)

        # hash 515319fa0ab47f372f6159bcc8ac27b43ee8a0ed corresponds to the commit on master branch
        assert_command(["fork-point", 'develop'], "515319fa0ab47f372f6159bcc8ac27b43ee8a0ed\n", strip_indentation=False)

        assert_command(["fork-point", 'refs/heads/develop'], "515319fa0ab47f372f6159bcc8ac27b43ee8a0ed\n", strip_indentation=False)

    def test_fork_point_override(self) -> None:
        """
        Verify behaviour of a 'git machete fork-point' command with fork-point being overridden by config key.
        """
        (
            self.repo_sandbox.new_branch("master")
                .commit("master first commit")
        )
        master_branch_first_commit_hash = get_current_commit_hash()
        self.repo_sandbox.commit("master second commit")
        develop_branch_fork_point = get_current_commit_hash()
        (
            self.repo_sandbox.new_branch("develop")
                .commit("develop commit")
        )
        launch_command('discover', '-y')

        # invalid fork point with length not equal to 40
        self.repo_sandbox.add_git_config_key('machete.overrideForkPoint.develop.to', 39 * 'a')
        assert launch_command('fork-point').strip() == develop_branch_fork_point

        # invalid, non-hexadecimal alphanumeric characters present in the fork point
        self.repo_sandbox.add_git_config_key('machete.overrideForkPoint.develop.to', 20 * 'g1')
        assert launch_command('fork-point').strip() == develop_branch_fork_point

        # invalid, non-hexadecimal special characters present in the fork point
        self.repo_sandbox.add_git_config_key('machete.overrideForkPoint.develop.to', 40 * '#')
        assert launch_command('fork-point').strip() == develop_branch_fork_point

        # valid commit hash but not present in the repository
        self.repo_sandbox.add_git_config_key('machete.overrideForkPoint.develop.to', 40 * 'a')
        assert launch_command('fork-point').strip() == (
               "Warn: since branch develop is no longer a descendant of commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, the fork point override to this commit no longer applies.\n"  # noqa: E501
               "Consider running:\n"
               "  git machete fork-point --unset-override develop\n\n" +
               develop_branch_fork_point)

        # valid fork-point override commit hash
        launch_command('fork-point', f'--override-to={master_branch_first_commit_hash}')
        assert launch_command('fork-point').strip() == master_branch_first_commit_hash
