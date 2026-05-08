from git_machete.annotation import Annotation
from git_machete.client.base import MacheteClient
from git_machete.git import Git, LocalBranchShortName

from .base_test import BaseTest
from .cli_runner import read_branch_layout_file, rewrite_branch_layout_file
from .git_repository import (check_out, commit, create_repo_with_remote,
                             new_branch, push)


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
        machete_client = MacheteClient(Git())
        machete_client.read_branch_layout_file(interactively_slide_out_invalid_branches=False)

        def anno(branch_name: str) -> Annotation:
            result = machete_client._state.get_annotation(LocalBranchShortName.of(branch_name))
            assert result is not None
            return result

        assert anno('feature2').unformatted_full_text == 'annotation'
        assert anno('feature2').qualifiers.rebase is True
        assert anno('feature2').qualifiers.push is True
        assert anno('feature2').text_without_qualifiers == 'annotation'
        assert str(anno('feature2').qualifiers) == ''

        assert anno('feature3').unformatted_full_text == 'annotation rebase=no push=no'
        assert anno('feature3').qualifiers.rebase is False
        assert anno('feature3').qualifiers.push is False
        assert anno('feature3').text_without_qualifiers == 'annotation'
        assert str(anno('feature3').qualifiers) == 'rebase=no push=no'

        assert anno('feature4').unformatted_full_text == 'annotation rebase=no push=no'
        assert anno('feature4').qualifiers.rebase is False
        assert anno('feature4').qualifiers.push is False
        assert anno('feature4').text_without_qualifiers == 'annotation'
        assert str(anno('feature4').qualifiers) == 'rebase=no push=no'

        assert anno('feature5').unformatted_full_text == 'annotation1 annotation2 annotation3 rebase=no push=no'
        assert anno('feature5').qualifiers.rebase is False
        assert anno('feature5').qualifiers.push is False
        assert anno('feature5').text_without_qualifiers == 'annotation1 annotation2 annotation3'
        assert str(anno('feature5').qualifiers) == 'rebase=no push=no'

        assert anno('feature6').unformatted_full_text == 'annotation1 rebase=nopush=no annotation2'
        assert anno('feature6').qualifiers.rebase is True
        assert anno('feature6').qualifiers.push is True
        assert anno('feature6').text_without_qualifiers == 'annotation1 rebase=nopush=no annotation2'
        assert str(anno('feature6').qualifiers) == ''

        assert anno('feature7').unformatted_full_text == 'annotation1rebase=no push=noannotation2'
        assert anno('feature7').qualifiers.rebase is True
        assert anno('feature7').qualifiers.push is True
        assert anno('feature7').text_without_qualifiers == 'annotation1rebase=no push=noannotation2'
        assert str(anno('feature7').qualifiers) == ''

        assert anno('feature8').unformatted_full_text == 'annotation rebase=no push=no'
        assert anno('feature8').qualifiers.rebase is False
        assert anno('feature8').qualifiers.push is False
        assert anno('feature8').text_without_qualifiers == 'annotation'
        assert str(anno('feature8').qualifiers) == 'rebase=no push=no'

    def test_branch_layout_leading_hash_comment_lines_ignored(self) -> None:
        create_repo_with_remote()
        new_branch('master')
        commit()
        push()
        new_branch('develop')
        commit()
        new_branch('feature')
        commit()
        check_out('master')

        rewrite_branch_layout_file(
            """
            master
            # develop
              feature
            """)
        machete_client = MacheteClient(Git())
        machete_client.read_branch_layout_file(interactively_slide_out_invalid_branches=False)

        assert machete_client.managed_branches == [
            LocalBranchShortName.of('master'),
            LocalBranchShortName.of('feature'),
        ]
        assert machete_client.children_of(LocalBranchShortName.of('master')) == [
            LocalBranchShortName.of('feature')]

    def test_branch_layout_hash_not_leading_whitespace_is_branch_or_annotation(self) -> None:
        create_repo_with_remote()
        new_branch('master')
        commit()
        push()
        new_branch('feature')
        commit()
        check_out('master')

        rewrite_branch_layout_file(
            """
            master
            feature  note #123
            """)
        machete_client = MacheteClient(Git())
        machete_client.read_branch_layout_file(interactively_slide_out_invalid_branches=False)

        feature = LocalBranchShortName.of('feature')
        assert machete_client.managed_branches == [
            LocalBranchShortName.of('master'),
            feature,
        ]
        assert machete_client._state.get_annotation(feature) is not None
        assert machete_client._state.get_annotation(feature).unformatted_full_text == 'note #123'  # type: ignore[union-attr]

    def test_save_branch_layout_file_does_not_preserve_hash_comment_lines(self) -> None:
        create_repo_with_remote()
        new_branch('master')
        commit()
        push()
        new_branch('feature')
        commit()
        check_out('master')

        rewrite_branch_layout_file(
            """
            master
            # feature
            """)
        machete_client = MacheteClient(Git())
        machete_client.read_branch_layout_file(interactively_slide_out_invalid_branches=False)
        machete_client.save_branch_layout_file()

        assert '#' not in read_branch_layout_file()
        assert read_branch_layout_file() == "master\n"
