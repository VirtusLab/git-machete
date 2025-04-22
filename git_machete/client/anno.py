from typing import List

from git_machete.annotation import Annotation
from git_machete.client.with_code_hosting import MacheteClientWithCodeHosting
from git_machete.git_operations import LocalBranchShortName


class AnnoMacheteClient(MacheteClientWithCodeHosting):
    def annotate(self, branch: LocalBranchShortName, words: List[str]) -> None:
        if branch in self._state.annotations and words == ['']:
            del self._state.annotations[branch]
        else:
            self._state.annotations[branch] = Annotation.parse(" ".join(words))
        self.save_branch_layout_file()

    def print_annotation(self, branch: LocalBranchShortName) -> None:
        if branch in self._state.annotations:
            print(self._state.annotations[branch].text_without_qualifiers)
