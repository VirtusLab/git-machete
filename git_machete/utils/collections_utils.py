"""Generic collection / iteration helpers."""

import itertools
from typing import (Any, Callable, Iterable, List, Optional, Sequence, Tuple,
                    TypeVar)

T = TypeVar('T')
U = TypeVar('U')


def excluding(iterable: Iterable[T], s: Iterable[T]) -> List[T]:
    return list(filter(lambda x: x not in s, iterable))


def flat_map(func: Callable[[T], List[T]], iterable: Iterable[T]) -> List[T]:
    return list(itertools.chain.from_iterable(map(func, iterable)))


def find_or_none(func: Callable[[T], bool], iterable: Iterable[T]) -> Optional[T]:
    return next(filter(func, iterable), None)  # type: ignore [arg-type]


def index_or_none(seq: Sequence[T], value: T) -> Optional[int]:
    try:
        return seq.index(value)
    except ValueError:
        return None


def map_truthy_only(func: Callable[[T], Optional[U]], iterable: Iterable[T]) -> List[U]:
    return list(filter(None, map(func, iterable)))


def get_non_empty_lines(s: str) -> List[str]:
    return list(filter(None, s.splitlines()))


# Converts a lambda accepting N arguments to a lambda accepting one argument, an N-element tuple.
# Name matching Scala's `tupled` on `FunctionX`.
def tupled(f: Callable[..., T]) -> Callable[[Any], T]:
    return lambda tple: f(*tple)


def get_second(pair: Tuple[Any, T]) -> T:
    _, b = pair
    return b
