from .mockers import (GitRepositorySandbox, assert_command, launch_command)

import os


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
        (
            self.repo_sandbox.new_branch("master")
                .add_file_with_content_and_commit(message="master commit.")
                .new_branch("develop")
                .add_file_with_content_and_commit(file_content='develop content', message="develop commit.")
                .new_branch("feature")
                .commit('feature commit.')
        )
        launch_command('discover', '-y')

        # Test `git machete fork-point` without providing the branch name
        # hash 67007ed30def3b9b658380b895a9f62b525286e0 corresponds to the commit on develop branch
        assert_command(["fork-point"], "67007ed30def3b9b658380b895a9f62b525286e0\n", strip_indentation=False)

        # hash 515319fa0ab47f372f6159bcc8ac27b43ee8a0ed corresponds to the commit on master branch
        assert_command(["fork-point", 'develop'], "515319fa0ab47f372f6159bcc8ac27b43ee8a0ed\n", strip_indentation=False)

        assert_command(["fork-point", 'refs/heads/develop'], "515319fa0ab47f372f6159bcc8ac27b43ee8a0ed\n", strip_indentation=False)
