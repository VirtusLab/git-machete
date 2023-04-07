from textwrap import dedent
from typing import Dict

from git_machete.annotation import Annotation
from git_machete.client import MacheteClient
from git_machete.git_operations import GitContext, LocalBranchShortName

from .mockers import GitRepositorySandbox, rewrite_definition_file


class TestClient:

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

    def test_annotations_read_definition_file(self) -> None:
        """
        Verify behaviour of a 'MacheteClient.read_definition_file()' method
        """
        (
            self.repo_sandbox
                .new_branch('master')
                .commit()
                .push()
                .new_branch('feature1')
                .commit()
                .new_branch('feature2')
                .commit()
                .check_out("master")
                .new_branch('feature3')
                .commit()
                .push()
                .new_branch('feature4')
                .commit()
                .check_out("master")
                .new_branch('feature5')
                .commit()
                .check_out("master")
                .new_branch('feature6')
                .commit()
                .check_out("master")
                .new_branch('feature7')
                .commit()
                .check_out("master")
                .new_branch('feature8')
                .commit()
        )

        body: str = \
            """
            master
            feature1
            feature2 annotation
            feature3 annotation rebase=no push=no
            feature4 rebase=no push=no annotation
            feature5 annotation1 rebase=no annotation2 push=no annotation3
            feature6 annotation1 rebase=nopush=no annotation2
            feature7 annotation1rebase=no push=noannotation2
            feature8 annotation rebase=no push=no rebase=no push=no
            """
        self.repo_sandbox.new_branch("root")
        rewrite_definition_file(body)
        git = GitContext()
        machete_client = MacheteClient(git)
        machete_client.read_definition_file(perform_interactive_slide_out=False)
        annotations: Dict[LocalBranchShortName, Annotation] = machete_client.annotations

        feature_2_branch = LocalBranchShortName.of('feature2')
        assert annotations[feature_2_branch].text == 'annotation'
        assert annotations[feature_2_branch].qualifiers.rebase is True
        assert annotations[feature_2_branch].qualifiers.push is True
        assert annotations[feature_2_branch].text_without_qualifiers == 'annotation'
        assert annotations[feature_2_branch].qualifiers_text == ''

        feature_3_branch = LocalBranchShortName.of('feature3')
        assert annotations[feature_3_branch].text == 'annotation rebase=no push=no'
        assert annotations[feature_3_branch].qualifiers.rebase is False
        assert annotations[feature_3_branch].qualifiers.push is False
        assert annotations[feature_3_branch].text_without_qualifiers == 'annotation'
        assert annotations[feature_3_branch].qualifiers_text == 'rebase=no push=no'

        feature_4_branch = LocalBranchShortName.of('feature4')
        assert annotations[feature_4_branch].text == 'rebase=no push=no annotation'
        assert annotations[feature_4_branch].qualifiers.rebase is False
        assert annotations[feature_4_branch].qualifiers.push is False
        assert annotations[feature_4_branch].text_without_qualifiers == 'annotation'
        assert annotations[feature_4_branch].qualifiers_text == 'rebase=no push=no'

        feature_5_branch = LocalBranchShortName.of('feature5')
        assert annotations[feature_5_branch].text == 'annotation1 rebase=no annotation2 push=no annotation3'
        assert annotations[feature_5_branch].qualifiers.rebase is False
        assert annotations[feature_5_branch].qualifiers.push is False
        assert annotations[feature_5_branch].text_without_qualifiers == 'annotation1 annotation2 annotation3'
        assert annotations[feature_5_branch].qualifiers_text == 'rebase=no push=no'

        feature_6_branch = LocalBranchShortName.of('feature6')
        assert annotations[feature_6_branch].text == 'annotation1 rebase=nopush=no annotation2'
        assert annotations[feature_6_branch].qualifiers.rebase is True
        assert annotations[feature_6_branch].qualifiers.push is True
        assert annotations[feature_6_branch].text_without_qualifiers == 'annotation1 rebase=nopush=no annotation2'
        assert annotations[feature_6_branch].qualifiers_text == ''

        feature_7_branch = LocalBranchShortName.of('feature7')
        assert annotations[feature_7_branch].text == 'annotation1rebase=no push=noannotation2'
        assert annotations[feature_7_branch].qualifiers.rebase is True
        assert annotations[feature_7_branch].qualifiers.push is True
        assert annotations[feature_7_branch].text_without_qualifiers == 'annotation1rebase=no push=noannotation2'
        assert annotations[feature_7_branch].qualifiers_text == ''

        feature_8_branch = LocalBranchShortName.of('feature8')
        assert annotations[feature_8_branch].text == 'annotation rebase=no push=no rebase=no push=no'
        assert annotations[feature_8_branch].qualifiers.rebase is False
        assert annotations[feature_8_branch].qualifiers.push is False
        assert annotations[feature_8_branch].text_without_qualifiers == 'annotation'
        assert annotations[feature_8_branch].qualifiers_text == 'rebase=no push=no'
