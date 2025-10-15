import json
import os
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.error import HTTPError

from git_machete.code_hosting import OrganizationAndRepository


class MockHTTPError(HTTPError):
    from email.message import Message

    def __init__(self, url: str, code: int, msg: Any, hdrs: Message, fp: Any) -> None:
        super().__init__(url, code, msg, hdrs, fp)
        self.msg = msg

    def read(self, _n: int = 1) -> bytes:  # noqa: F841
        return json.dumps(self.msg).encode()


class MockAPIResponse:
    def __init__(self,
                 status_code: int,
                 response_data: Union[List[Dict[str, Any]], Dict[str, Any]],
                 headers: Dict[str, Any] = {}) -> None:
        self.status_code = status_code
        self.response_data = response_data
        self.headers = headers

    def read(self) -> bytes:
        return json.dumps(self.response_data).encode()

    def info(self) -> Dict[str, Any]:
        return defaultdict(lambda: "", self.headers)


def mock_from_url(domain: str, url: str) -> "OrganizationAndRepository":  # noqa: U100
    if url[:8] == "https://":
        return OrganizationAndRepository(url.split("/")[3], url.split("/")[4].replace(".git", ""))
    dir_to_repo = {
        "remote": "example-repo",
        "remote-1": "example-repo-1",
        "remote-2": "example-repo-2",
        "second-remote": "second-example-repo",
    }
    dir = url.split(os.path.sep)[-1]
    return OrganizationAndRepository("example-org", dir_to_repo[dir])


def mock_shutil_which(path: Optional[str]) -> Callable[[Any], Optional[str]]:
    return lambda _cmd: path
