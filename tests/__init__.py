import pytest

# See https://docs.pytest.org/en/latest/how-to/writing_plugins.html#assertion-rewriting
pytest.register_assert_rewrite("tests.mockers")
