from typing import Dict

from git_machete.annotation import Annotation
from git_machete.client.base import MacheteClient
from git_machete.git_operations import GitContext, LocalBranchShortName

from .base_test import BaseTest
from .mockers import rewrite_branch_layout_file
from .mockers_git_repository import (check_out, commit,
                                     create_repo_with_remote, new_branch, push)


class TestClient(BaseTest):

    def test_annotations_read_branch_layout_file(self) -> None:
        """
        Verify behaviour of a 'MacheteClient.read_branch_layout_file()' method
        """
        create_repo_with_remote()
        new_branch('master')
        commit()
        push()
        new_branch('feature1')
        commit()
        new_branch('feature2')
        commit()
        check_out("master")
        new_branch('feature3')
        commit()
        push()
        new_branch('feature4')
        commit()
        check_out("master")
        new_branch('feature5')
        commit()
        check_out("master")
        new_branch('feature6')
        commit()
        check_out("master")
        new_branch('feature7')
        commit()
        check_out("master")
        new_branch('feature8')
        commit()

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
        rewrite_branch_layout_file(body)
        machete_client = MacheteClient(GitContext())
        machete_client.read_branch_layout_file(interactively_slide_out_invalid_branches=False)
        annotations: Dict[LocalBranchShortName, Annotation] = machete_client.annotations

        feature_2_branch = LocalBranchShortName.of('feature2')
        assert annotations[feature_2_branch].unformatted_full_text == 'annotation'
        assert annotations[feature_2_branch].qualifiers.rebase is True
        assert annotations[feature_2_branch].qualifiers.push is True
        assert annotations[feature_2_branch].text_without_qualifiers == 'annotation'
        assert str(annotations[feature_2_branch].qualifiers) == ''

        feature_3_branch = LocalBranchShortName.of('feature3')
        assert annotations[feature_3_branch].unformatted_full_text == 'annotation rebase=no push=no'
        assert annotations[feature_3_branch].qualifiers.rebase is False
        assert annotations[feature_3_branch].qualifiers.push is False
        assert annotations[feature_3_branch].text_without_qualifiers == 'annotation'
        assert str(annotations[feature_3_branch].qualifiers) == 'rebase=no push=no'

        feature_4_branch = LocalBranchShortName.of('feature4')
        assert annotations[feature_4_branch].unformatted_full_text == 'annotation rebase=no push=no'
        assert annotations[feature_4_branch].qualifiers.rebase is False
        assert annotations[feature_4_branch].qualifiers.push is False
        assert annotations[feature_4_branch].text_without_qualifiers == 'annotation'
        assert str(annotations[feature_4_branch].qualifiers) == 'rebase=no push=no'

        feature_5_branch = LocalBranchShortName.of('feature5')
        assert annotations[feature_5_branch].unformatted_full_text == 'annotation1 annotation2 annotation3 rebase=no push=no'
        assert annotations[feature_5_branch].qualifiers.rebase is False
        assert annotations[feature_5_branch].qualifiers.push is False
        assert annotations[feature_5_branch].text_without_qualifiers == 'annotation1 annotation2 annotation3'
        assert str(annotations[feature_5_branch].qualifiers) == 'rebase=no push=no'

        feature_6_branch = LocalBranchShortName.of('feature6')
        assert annotations[feature_6_branch].unformatted_full_text == 'annotation1 rebase=nopush=no annotation2'
        assert annotations[feature_6_branch].qualifiers.rebase is True
        assert annotations[feature_6_branch].qualifiers.push is True
        assert annotations[feature_6_branch].text_without_qualifiers == 'annotation1 rebase=nopush=no annotation2'
        assert str(annotations[feature_6_branch].qualifiers) == ''

        feature_7_branch = LocalBranchShortName.of('feature7')
        assert annotations[feature_7_branch].unformatted_full_text == 'annotation1rebase=no push=noannotation2'
        assert annotations[feature_7_branch].qualifiers.rebase is True
        assert annotations[feature_7_branch].qualifiers.push is True
        assert annotations[feature_7_branch].text_without_qualifiers == 'annotation1rebase=no push=noannotation2'
        assert str(annotations[feature_7_branch].qualifiers) == ''

        feature_8_branch = LocalBranchShortName.of('feature8')
        assert annotations[feature_8_branch].unformatted_full_text == 'annotation rebase=no push=no'
        assert annotations[feature_8_branch].qualifiers.rebase is False
        assert annotations[feature_8_branch].qualifiers.push is False
        assert annotations[feature_8_branch].text_without_qualifiers == 'annotation'
        assert str(annotations[feature_8_branch].qualifiers) == 'rebase=no push=no'
