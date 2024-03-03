from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

import pytest

from . import __dump__, add_debug_line

if TYPE_CHECKING:
    from collections.abc import Generator
    from typing import Any


class Dumper:
    def __init__(self):
        self.buffer = StringIO()

    def __call__(self, name: str, value: Any) -> None:
        self.buffer.write(add_debug_line(name, value))
        self.buffer.write('\n')
        self.buffer.flush()

    def get(self) -> str:
        ret = self.buffer.getvalue()
        self.buffer.truncate(0)
        return ret


DUMPER: pytest.StashKey[Dumper] = pytest.StashKey()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item: pytest.Item) -> Generator[None, None, None]:
    item.stash.setdefault(DUMPER, Dumper())
    yield


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item: pytest.Item) -> Generator[None, None, None]:
    # teardown of fixtures
    yield
    # now the fixtures have executed their teardowns
    if DUMPER in item.stash:
        text = item.stash[DUMPER].get()
        item.add_report_section('teardown', f'dump[{item.nodeid}]', text)
        del item.stash[DUMPER]


@pytest.fixture(autouse=True, name=__dump__)
def dumper_fixture_impl(request: pytest.FixtureRequest) -> Generator[Dumper, None, None]:
    return request.node.stash.setdefault(DUMPER, Dumper())
