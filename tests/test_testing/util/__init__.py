from __future__ import annotations

import os
import re
import shutil
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, TypeVar, final, overload

import pytest

import sphinx

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import Any, Final

    from _pytest.pytester import Pytester, RunResult

SPHINX_LIBDIR_PATH: Final[str] = str(Path(sphinx.__file__).parent)

# delimiters where debug content is printed
DEBUG_MARK: Final[str] = '[sphinx-dump-channel] '
_SAFE_MARK: Final[str] = re.escape(DEBUG_MARK)
__dump__: Final[str] = '__dumper_fixture__'

T = TypeVar('T')


@final
class _SourceInfo(NamedTuple):
    path: str
    namespace: str
    env_crc32: int
    srcdir_id: str

    def sameinfo(self, other: _SourceInfo) -> bool:
        return isinstance(other, _SourceInfo) and other[1:] == self[1:]


def SourceInfo(path: str) -> _SourceInfo:
    abspath = Path(path).absolute()

    namespace = abspath.parent.parent.stem
    try:
        uuid.UUID(namespace, version=5)
    except ValueError:
        pytest.fail(f'cannot extract namespace ID from: {path!r}')

    env_crc32 = abspath.parent.stem
    if not env_crc32 or not env_crc32.isnumeric():
        pytest.fail(f'cannot extract configuration checksum from: {path!r}')

    return _SourceInfo(str(abspath), namespace, int(env_crc32), abspath.stem)


def add_debug_line(name: str, value: Any) -> str:
    return f'{DEBUG_MARK}{name}={value}'



# TODO: handle pythonpaths
def _runpytest(pytester: Pytester, /, *args: str | os.PathLike[str], **kwargs: Any) -> RunResult:
    # use '-rA' to show the dumper's reports before intercepting them
    os.environ['COLUMNS'] = str(shutil.get_terminal_size()[0])
    return pytester.runpytest(*args, '-rA', **kwargs)


def integration(pytester: Pytester, *, count: int) -> Output:
    # use '-rA' to show the dumper's reports
    res = _runpytest(pytester, plugins=['sphinx.testing.plugin'])
    res.assert_outcomes(passed=count)
    return Output(res)


def xdist_integration(pytester: Pytester, *, count: int, jobs: int = 2) -> Output:
    res = _runpytest(pytester, '-n', str(jobs), '--dist=loadgroup',
                     plugins=['sphinx.testing.plugin', 'xdist'])
    res.assert_outcomes(passed=count)
    return Output(res)


class Output:
    def __init__(self, res: RunResult) -> None:
        self.res = res
        self.lines = tuple(res.outlines)

    @overload
    def find(self, name: str, pattern: str = ..., *, type: None = ...) -> str | None: ...  # NoQA: E301, E704
    @overload
    def find(self, name: str, pattern: str = ..., *, type: Callable[[str], T]) -> T | None: ...  # NoQA: E301, E704
    def find(  # NoQA: E301
        self,
        name: str,
        pattern: str = r'.*',
        *,
        type: Callable[[str], Any] | None = None,
    ) -> Any:
        return next(iter(self.findall(name, pattern, type=type)), None)

    @overload
    def findall(self, name: str, pattern: str = ..., *, type: None = ...) -> Sequence[str]: ...  # NoQA: E301, E704
    @overload
    def findall(self, name: str, pattern: str = ..., *, type: Callable[[str], T]) -> Sequence[T]: ...  # NoQA: E301, E704
    def findall(  # NoQA: E301
        self,
        name: str,
        pattern: str = r'.*',
        *,
        type: Callable[[str], Any] | None = None,
    ) -> Sequence[Any]:
        name = re.escape(name)
        p = re.compile(f'^{_SAFE_MARK}{name}=({pattern})$')
        matches = filter(None, map(p.match, self.lines))
        values = (m.group(1) for m in matches)
        return tuple(map(type, values)) if callable(type) else tuple(values)
