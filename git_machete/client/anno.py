from typing import List, Optional

from git_machete.annotation import Annotation
from git_machete.client.with_code_hosting import MacheteClientWithCodeHosting
from git_machete.git import LocalBranchShortName


class AnnoMacheteClient(MacheteClientWithCodeHosting):
    def annotate(self, *, opt_branch: Optional[LocalBranchShortName], words: List[str]) -> None:
        branch = self.expect_in_managed_branches(opt_branch or self._git.get_current_branch())
        if self._state.has_annotation(branch) and words == ['']:
            self._state.delete_annotation(branch)
        else:
            self._state.set_annotation(branch, Annotation.parse(" ".join(words)))
        self.save_branch_layout_file()

    def print_annotation(self, *, opt_branch: Optional[LocalBranchShortName]) -> None:
        branch = self.expect_in_managed_branches(opt_branch or self._git.get_current_branch())
        anno = self._state.get_annotation(branch)
        if anno is not None:
            print(anno.text_without_qualifiers)
