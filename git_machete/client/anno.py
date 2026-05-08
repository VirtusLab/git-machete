from typing import List

from git_machete.annotation import Annotation
from git_machete.client.with_code_hosting import MacheteClientWithCodeHosting
from git_machete.git import LocalBranchShortName


class AnnoMacheteClient(MacheteClientWithCodeHosting):
    def annotate(self, branch: LocalBranchShortName, words: List[str]) -> None:
        if self._state.has_annotation(branch) and words == ['']:
            self._state.delete_annotation(branch)
        else:
            self._state.set_annotation(branch, Annotation.parse(" ".join(words)))
        self.save_branch_layout_file()

    def print_annotation(self, branch: LocalBranchShortName) -> None:
        anno = self._state.get_annotation(branch)
        if anno is not None:
            print(anno.text_without_qualifiers)
