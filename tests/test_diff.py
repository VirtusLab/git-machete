import io
import sys
from typing import Any

import cli
from .mockers import (GitRepositorySandbox, assert_command, launch_command,
                      mock_run_cmd)


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

        (
            self.repo_sandbox.new_branch("master")
                .add_file_with_content_and_commit(message='master commit1')
                .push()
                .new_branch("develop")
                .add_file_with_content_and_commit(file_name='develop_file_name.txt', file_content='Develop content', message='develop commit')
                .push()
        )
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

        print('launch')
        launch_command('diff', 'develop')
        old_stdout = sys.stdout
        new_stdout = io.StringIO()
        sys.stdout = new_stdout

        print('xd')
        print(launch_command('diff', 'develop'))
        cli.launch(['diff', 'develop'])
        print('xd')

        output = new_stdout.getvalue()

        sys.stdout = old_stdout
        print(output)
        print()
        assert_command(["diff", "develop"], expected_status_output)
