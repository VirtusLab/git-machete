from enum import Enum
from typing import Optional, Type, TypeVar

from git_machete.exceptions import MacheteException

DISCOVER_DEFAULT_FRESH_BRANCH_COUNT = 10
MAX_COMMITS_FOR_SQUASH_MERGE_DETECTION = 1000
INITIAL_COMMIT_COUNT_FOR_LOG = 10
TOTAL_COMMIT_COUNT_FOR_LOG = 100

E = TypeVar('E', bound='Enum')


class ParsableEnum(Enum):
    @classmethod
    def from_string(cls: Type[E], value: str, from_where: Optional[str]) -> E:
        try:
            return cls[value.upper()]
        except KeyError:
            valid_values = ', '.join(e.value for e in cls)
            prefix = f"Invalid value for {from_where}" if from_where else "Invalid value"
            raise MacheteException(f"{prefix}: `{value}`. Valid values are `{valid_values}`")


class SquashMergeDetection(ParsableEnum):
    NONE = "none"
    SIMPLE = "simple"
    EXACT = "exact"
