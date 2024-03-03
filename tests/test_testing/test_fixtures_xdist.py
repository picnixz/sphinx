from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, NamedTuple

import pytest

from .util import SourceInfo, __dump__, xdist_integration

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Final, Literal, Union

    from _pytest.pytester import Pytester

    from .util import Output, _SourceInfo

    GroupPolicy = Union[int, Literal['sphinx', 'xdist']]

FOO: Final[str] = 'foo'
BAR: Final[str] = 'bar'

GROUP_POLICIES: Final[tuple[GroupPolicy, ...]] = (1234, 'sphinx', 'xdist')


@pytest.fixture(autouse=True)
def pytester_source_override(pytester: Pytester, pytester_source: Path) -> Path:
    source = pytester_source.read_text('utf-8') + '''
pytest_plugins = [*pytest_plugins, 'xdist']
'''
    return pytester.makeconftest(source)


def _filecontent(
    testid: str,
    *,
    parametrized: bool,
    group: int | Literal['sphinx', 'xdist'],
) -> str:
    fixture_list = [__dump__, 'request', 'app', 'worker_id']

    if group == 'xdist':
        # do not use the auto strategy
        xdist_group_mark = '@pytest.mark.sphinx_no_default_xdist()'
    elif group == 'sphinx':
        # use the auto-strategy by Sphinx
        xdist_group_mark = ''
    else:
        xdist_group_mark = f'@pytest.mark.xdist_group("@{group!s}")'

    if parametrized:
        parametrize_mark = "@pytest.mark.parametrize('value', [1, 2])"
        fixture_list.append('value')
    else:
        parametrize_mark = None

    marks = '\n'.join(filter(None, (xdist_group_mark, parametrize_mark)))
    fixtures = ', '.join(fixture_list)

    return f'''
import pytest

{marks}
@pytest.mark.sphinx('dummy')
@pytest.mark.test_params()  # ensure an isolation of the tests
def test_group_{testid}({fixtures}):
    assert 0
    assert request.config.pluginmanager.has_plugin('xdist')
    assert hasattr(request.config, 'workerinput')

    {__dump__}({testid!r}, str(app.srcdir))
    {__dump__}(f'nid[{testid}]', request.node.nodeid)
    {__dump__}(f'wid[{testid}]', worker_id)
'''


class ExtractInfo(NamedTuple):
    source: _SourceInfo
    workid: str
    nodeid: str

    @property
    def loader(self) -> str | None:
        parts = self.nodeid.rsplit('@', maxsplit=1)
        assert len(parts) == 2 or parts == [self.nodeid]
        return parts[1] if len(parts) == 2 else None


def extract_infos(output: Output, name: str, *, n: int = 1) -> list[ExtractInfo]:
    srcs = output.findall(name, type=SourceInfo)
    assert len(srcs) == n
    assert all(srcs)

    wids = output.findall(f'wid[{name}]')
    assert len(wids) == n
    assert all(wids)

    nids = output.findall(f'nid[{name}]')
    assert len(nids) == n
    assert all(nids)

    return [
        ExtractInfo(source, workid, nodeid)
        for source, workid, nodeid in zip(srcs, wids, nids)
    ]


def check_native_policy(items: list[ExtractInfo]) -> None:
    # different xdist auto-generated group (which is None by default
    # to indicate that the user did not specify any ``xdist_group``)
    loaders = {item.loader for item in items}
    assert loaders == {None}


def check_sphinx_policy(items: list[ExtractInfo]) -> None:
    # same sphinx auto-generated group since same location
    loaders = {item.loader for item in items}
    assert len(loaders) == 1


def check_marker_policy(items: list[ExtractInfo], group_name: str) -> None:
    loaders = {item.loader for item in items}
    assert loaders == {group_name}


class TestParallelTestingModule:
    @staticmethod
    def run(
        pytester: Pytester, grp1: GroupPolicy, grp2: GroupPolicy, parametrized: bool, count: int,
    ) -> Output:
        c1 = _filecontent(FOO, group=grp1, parametrized=parametrized)
        c2 = _filecontent(BAR, group=grp2, parametrized=parametrized)
        pytester.makepyfile('\n'.join((c1, c2)))
        return xdist_integration(pytester, count=count)

    @pytest.mark.parametrize('group', GROUP_POLICIES)
    def test_no_parametrization(self, pytester: Pytester, group: GroupPolicy) -> None:
        output = self.run(pytester, group, group, parametrized=False, count=2)
        foo = extract_infos(output, FOO)[0]
        bar = extract_infos(output, BAR)[0]

        assert foo.source.sameinfo(bar.source)

        if group in {'xdist', 'sphinx'}:
            # since we are not parametrizing, sphinx never adds a group
            assert foo.workid != bar.workid
            assert foo.loader is None
            assert bar.loader is None
        else:
            # explicit group + loadgroup policy
            assert foo.workid == bar.workid
            assert foo.loader == str(group)
            assert bar.loader == str(group)

    @pytest.mark.parametrize(('grp1', 'grp2'), [
        *zip(GROUP_POLICIES, GROUP_POLICIES),
        *itertools.combinations(GROUP_POLICIES, 2),
    ])
    def test_with_parametrization(
        self, pytester: Pytester, grp1: GroupPolicy, grp2: GroupPolicy,
    ) -> None:
        output = self.run(pytester, grp1, grp2, parametrized=True, count=4)
        foo = extract_infos(output, FOO, n=2)
        bar = extract_infos(output, BAR, n=2)

        for items in (foo, bar):
            for x, y in itertools.combinations(items, 2):
                assert x.nodeid != y.nodeid
                assert x.source.sameinfo(y.source)

                assert x.workid in x.source.path
                temp = x.source.path.replace(x.workid, y.workid, 1)
                assert temp == y.source.path

                assert y.workid in y.source.path
                temp = y.source.path.replace(y.workid, x.workid, 1)
                assert temp == x.source.path

        for x, y in itertools.combinations((*foo, *bar), 2):
            # inter-collectors also have the same source info
            # except for the node location (fspath, lineno)
            assert x.source.sameinfo(y.source)

        for group_type, items in ((grp1, foo), (grp2, bar)):
            if group_type == 'xdist':
                check_native_policy(items)
            elif group_type == 'sphinx':
                check_sphinx_policy(items)
            else:
                assert isinstance(group_type, int)
                check_marker_policy(items, str(group_type))

        group: str | int
        if (group := grp1) == grp2:
            if group == 'xdist' or isinstance(group, int):
                assert {x.loader for x in foo} == {x.loader for x in bar}
            else:
                assert len({x.loader for x in foo}) == 1
                assert len({x.loader for x in bar}) == 1
                assert {x.loader for x in foo} != {x.loader for x in bar}


class TestParallelTestingPackage:
    @staticmethod
    def run(
        pytester: Pytester, grp1: GroupPolicy, grp2: GroupPolicy, parametrized: bool, count: int,
    ) -> Output:
        pytester.makepyfile(**{
            'test_group_a/test_foo': _filecontent(FOO, group=grp1, parametrized=parametrized),
            'test_group_b/test_bar': _filecontent(BAR, group=grp2, parametrized=parametrized),
        })
        return xdist_integration(pytester, count=count)

    @pytest.mark.parametrize('group', GROUP_POLICIES)
    def test_no_parametrization(self, pytester: Pytester, group: GroupPolicy) -> None:
        output = self.run(pytester, group, group, parametrized=False, count=2)
        foo = extract_infos(output, FOO)[0]
        bar = extract_infos(output, BAR)[0]

        assert foo.source.namespace != bar.source.namespace
        assert foo.source.env_crc32 == bar.source.env_crc32
        assert foo.source.srcdir_id == bar.source.srcdir_id

        if group in {'xdist', 'sphinx'}:
            # since we are not parametrizing, sphinx never adds a group
            assert foo.workid != bar.workid
            assert foo.loader is None
            assert bar.loader is None
        else:
            # explicit group + loadgroup policy
            assert foo.workid == bar.workid
            assert foo.loader == str(group)
            assert bar.loader == str(group)

    @pytest.mark.parametrize(('grp1', 'grp2'), [
        *zip(GROUP_POLICIES, GROUP_POLICIES),
        *itertools.combinations(GROUP_POLICIES, 2),
    ])
    def test_with_parametrization(
        self, pytester: Pytester, grp1: GroupPolicy, grp2: GroupPolicy,
    ) -> None:
        output = self.run(pytester, grp1, grp2, parametrized=True, count=4)
        foo = extract_infos(output, FOO, n=2)
        bar = extract_infos(output, BAR, n=2)

        for items in (foo, bar):
            for x, y in itertools.combinations(items, 2):
                assert x.source.sameinfo(y.source)
                assert x.workid in x.source.path
                temp = x.source.path.replace(x.workid, y.workid, 1)
                assert temp == y.source.path

                assert y.workid in y.source.path
                temp = y.source.path.replace(y.workid, x.workid, 1)
                assert temp == x.source.path

        for x, y in itertools.product(foo, bar):
            assert not x.source.sameinfo(y.source)

        for group_type, items in ((grp1, foo), (grp2, bar)):
            if group_type == 'xdist':
                check_native_policy(items)
            elif group_type == 'sphinx':
                check_sphinx_policy(items)
            else:
                assert isinstance(group_type, int)
                check_marker_policy(items, str(group_type))

        group: str | int
        if (group := grp1) == grp2:
            if group == 'xdist' or isinstance(group, int):
                assert {x.loader for x in foo} == {x.loader for x in bar}
            else:
                assert len({x.loader for x in foo}) == 1
                assert len({x.loader for x in bar}) == 1
                assert {x.loader for x in foo} != {x.loader for x in bar}
