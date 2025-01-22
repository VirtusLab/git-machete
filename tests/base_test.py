import os
from typing import Any, Set

from pytest_mock import MockerFixture


class BaseTest:
    def setup_method(self) -> None:
        self.expected_mock_methods: Set[str] = set()
        # So that env vars coming from outside don't interfere with the tests.
        # Note that this is only relevant in plain `pytest` invocations as `tox` doesn't pass env vars from the outside env by default.
        for env_var in ["GIT_MACHETE_EDITOR", "GIT_MACHETE_REBASE_OPTS", "GITHUB_TOKEN", "GITLAB_TOKEN"]:
            os.environ.pop(env_var, None)

    def patch_symbol(self, mocker: MockerFixture, symbol: str, target: Any) -> None:
        if callable(target):
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                if symbol in self.expected_mock_methods:
                    self.expected_mock_methods.remove(symbol)
                return target(*args, **kwargs)
            mocker.patch(symbol, wrapper)
            self.expected_mock_methods.add(symbol)
        else:
            mocker.patch(symbol, target)

    def teardown_method(self) -> None:
        if len(self.expected_mock_methods) == 1:
            raise Exception("Patched method has never been called: " + list(self.expected_mock_methods)[0])
        elif len(self.expected_mock_methods) > 1:
            raise Exception("Patched methods have never been called: " + ", ".join(self.expected_mock_methods))
