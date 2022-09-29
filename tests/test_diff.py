from typing import Any

from .mockers import (GitRepositorySandbox, assert_command, mock_run_cmd_and_forward_stdout)


class TestDiff:

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

    def test_diff(self, mocker: Any) -> None:
        """
        Verify behaviour of a 'git machete diff' command.
        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_forward_stdout)  # to hide git outputs in tests
        (
            self.repo_sandbox.new_branch("master")
                .add_file_with_content_and_commit(message='master commit1')
                .push()
                .new_branch("develop")
                .add_file_with_content_and_commit(file_name='develop_file_name.txt',
                                                  file_content='Develop content\n',
                                                  message='develop commit')
                .push()
                .write_to_file(file_name='file_name.txt',
                               file_content='Content not committed\n')
        )

        expected_status_output = """
        diff --git a/develop_file_name.txt b/develop_file_name.txt
        new file mode 100644
        index 0000000..a3bd4e5
        --- /dev/null
        +++ b/develop_file_name.txt
        @@ -0,0 +1 @@
        +Develop content
        diff --git a/file_name.txt b/file_name.txt
        index ff98b6d..5c3aa83 100644
        --- a/file_name.txt
        +++ b/file_name.txt
        @@ -1 +1 @@
        -Some file content
        +Content not committed

        """

        # Test `git machete diff` without providing the branch name, git diff against the current working tree
        assert_command(["diff"], expected_status_output, indent='')

        expected_status_output = """
        diff --git a/develop_file_name.txt b/develop_file_name.txt
        new file mode 100644
        index 0000000..a3bd4e5
        --- /dev/null
        +++ b/develop_file_name.txt
        @@ -0,0 +1 @@
        +Develop content

        """

        assert_command(["diff", "develop"], expected_status_output, indent='')

        assert_command(["diff", "refs/heads/develop"], expected_status_output, indent='')
