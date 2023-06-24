from pytest_mock import MockerFixture

from .base_test import BaseTest
from .mockers import assert_success, mock__run_cmd_and_forward_stdout


class TestDiff(BaseTest):

    def test_diff(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.utils._run_cmd', mock__run_cmd_and_forward_stdout)  # to capture `git diff` outputs
        (
            self.repo_sandbox.new_branch("master")
                .add_file_and_commit(message='master commit1')
                .push()
                .new_branch("develop")
                .add_file_and_commit(file_path='develop_file_name.txt',
                                     file_content='Develop content\n',
                                     message='develop commit')
                .push()
                .write_to_file(file_path='file_name.txt',
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
        assert_success(["diff"], expected_status_output)

        expected_status_output = """
        diff --git a/develop_file_name.txt b/develop_file_name.txt
        new file mode 100644
        index 0000000..a3bd4e5
        --- /dev/null
        +++ b/develop_file_name.txt
        @@ -0,0 +1 @@
        +Develop content
        """
        assert_success(["diff", "develop"], expected_status_output)
        assert_success(["diff", "refs/heads/develop"], expected_status_output)

        assert_success(
            ["diff", "--stat", "refs/heads/develop"],
            "develop_file_name.txt | 1 +\n"
            "1 file changed, 1 insertion(+)\n"
        )
