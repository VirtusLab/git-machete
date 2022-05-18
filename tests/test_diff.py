import io
import os
import sys
import textwrap
from typing import Any

from .mockers import (adapt, GitRepositorySandbox, assert_command, launch_command,
                      launch_command1, mock_run_cmd, mock_run_cmd_and_forward_stdout)


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
                .add_file_with_content_and_commit(file_name='develop_file_name.txt', file_content='Develop content', message='develop commit')
                .push()
        )

        # Test `git machete diff` without providing branch name
        # assert_command(["diff"], '')

        expected_status_output = (
            """
            diff --git a/develop_file_name.txt b/develop_file_name.txt
            new file mode 100644
            index 0000000..a3bd4e5
            --- /dev/null
            +++ b/develop_file_name.txt
            @@ -0,0 +1 @@
            +Develop content
            """
        )
        print()

        x = launch_command('diff', 'develop')
        print()

        # self.repo_sandbox.execute('git machete version > boo.txt')
        # with open('boo.txt', 'r') as f:
        #     git_diff_output = ''.join(f.readlines())
        #     print(git_diff_output)
        # self.repo_sandbox.execute('git machete diff develop > foo.txt')
        # with open('foo.txt', 'r') as f:
        #     git_diff_output = ''.join(f.readlines())
        # assert textwrap.dedent(expected_status_output.replace('\n', '', 1)) == git_diff_output

        # launch_command('diff', 'develop', '>', 'foo.txt')
        # with open('foo.txt', 'r') as f:
        #     x = ''.join(f.readlines())
        #     print('file content:\n', x)


        print('-')
        print('-')
        # with open('test.txt', 'w+') as f:
        #     print(launch_command('diff', 'develop'), file=f)
        #     # f.write('\ntest\ntest2\n')
        #
        # with open('test.txt', 'r') as f:
        #     x = f.readlines()
        #     print('file content:\n', x)

        # print('launch:', launch_command('diff', 'develop'))
        # launch_command('diff', 'develop')

        # old_stdout = sys.stdout
        # new_stdout = io.StringIO()
        # sys.stdout = new_stdout
        #
        # print()
        # print('xd')
        # print(launch_command('diff', 'develop'))
        # print('xd')
        #
        # output = new_stdout.getvalue()
        #
        # sys.stdout = old_stdout
        # print()
        # print('OUTPUT')
        # print(output)
        # print()
        # assert_command(["diff", "develop"], expected_status_output)
