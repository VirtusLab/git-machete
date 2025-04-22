from typing import Optional

from git_machete.client import MacheteClient
from git_machete.code_hosting import CodeHostingClient, CodeHostingSpec
from git_machete.utils import bold, debug


class MacheteClientWithCodeHosting(MacheteClient):
    def sync_annotations_to_prs(self, spec: CodeHostingSpec, include_urls: bool) -> None:
        self._init_code_hosting_client(spec)
        current_user: Optional[str] = self.code_hosting_client.get_current_user_login()
        debug(f'Current {spec.display_name} user is ' + (bold(current_user or '<none>')))
        all_open_prs = self.get_all_open_prs()
        self._sync_annotations_to_branch_layout_file(spec, all_open_prs, current_user, include_urls=include_urls, verbose=True)
