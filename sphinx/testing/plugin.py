from __future__ import annotations

import os
import shutil
import subprocess
import sys
from io import StringIO
from typing import TYPE_CHECKING, TypedDict

import pytest

from sphinx.testing._fixtures import AppParams, get_app_params, get_test_params
from sphinx.testing._isolation import Isolation
from sphinx.testing.pytest_util import TestRootFinder, find_context
from sphinx.testing.util import SphinxTestApp, SphinxTestAppLazyBuild

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path
    from typing import Any

    from sphinx.testing._fixtures import TestParams
    from sphinx.testing._isolation import IsolationPolicy

DEFAULT_ENABLED_MARKERS = [
    (
        'sphinx('
        'buildername="html", *, '
        'srcdir=None, testroot="root", confoverrides=None, '
        'freshenv=False, warningiserror=False, tags=None, '
        'verbosity=0, parallel=0, keep_going=False, '
        'builddir=None, docutils_conf=None, '
        'isolate=False): arguments to initialize the sphinx test application.'
    ),
    'test_params(shared_result=None): test configuration.',
    'isolate(policy=None, /): test isolation policy.',
]


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    for marker in DEFAULT_ENABLED_MARKERS:
        config.addinivalue_line('markers', marker)


@pytest.fixture(scope='session')
def sphinx_test_tempdir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Fixture for a temporary directory."""
    return tmp_path_factory.getbasetemp()


@pytest.fixture()
def sphinx_builder(request: pytest.FixtureRequest) -> str:
    """Fixture for the default builder name."""
    return getattr(request, 'param', 'html')


@pytest.fixture()
def sphinx_isolation(request: pytest.FixtureRequest) -> IsolationPolicy | None:
    """Fixture for the default isolation policy."""
    return getattr(request, 'param', False)


@pytest.fixture()
def rootdir(request: pytest.FixtureRequest) -> str | os.PathLike[str] | None:
    """Fixture for the directory containing the testroot directories."""
    return getattr(request, 'param', None)


@pytest.fixture()
def testroot_prefix(request: pytest.FixtureRequest) -> str | None:
    """Fixture for the testroot directories prefix."""
    return getattr(request, 'param', 'test-')


@pytest.fixture()
def default_testroot(request: pytest.FixtureRequest) -> str | None:
    """Dynamic fixture for the default testroot ID."""
    return getattr(request, 'param', 'root')


@pytest.fixture()
def testroot_finder(
    rootdir: str | os.PathLike[str] | None,
    testroot_prefix: str | None,
    default_testroot: str | None,
) -> TestRootFinder:
    """Fixture for the testroot finder object."""
    return TestRootFinder(rootdir, testroot_prefix, default_testroot)


class _CacheEntry(TypedDict):
    """Cached entry in a :class:`SharedResult`."""

    status: str
    """The application's status output."""
    warning: str
    """The application's warning output."""


class _CacheFrame(TypedDict):
    """The restored cached value."""

    status: StringIO
    """An I/O object initialized to the cached status output."""
    warning: StringIO
    """An I/O object initialized to the cached warning output."""


class ModuleCache:
    """:meta private:"""

    __slots__ = ('_cache',)

    def __init__(self) -> None:
        self._cache: dict[str, _CacheEntry] = {}

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()

    def store(self, key: str, app: SphinxTestApp) -> None:
        """Cache some attributes from *app* in the cache.

        :param key: The cache key (usually a ``shared_result``).
        :param app: An application whose attributes are cached.

        The application's attributes being cached are:

        * The string value of :attr:`SphinxTestApp.status`.
        * The string value of :attr:`SphinxTestApp.warning`.
        """
        if key not in self._cache:
            status, warning = app.status.getvalue(), app.warning.getvalue()
            self._cache[key] = {'status': status, 'warning': warning}

    def restore(self, key: str) -> _CacheFrame | None:
        """Reconstruct the cached attributes for *key*."""
        if key not in self._cache:
            return None

        data = self._cache[key]
        return {'status': StringIO(data['status']), 'warning': StringIO(data['warning'])}


def _init_sources(src: str | None, dst: Path, isolation: Isolation) -> None:
    if src is None or dst.exists():
        return

    if not os.path.exists(src):
        pytest.fail(f'no sources found at: {src!r}')

    # make a copy of the testroot
    shutil.copytree(src, dst)

    # make the files read-only if isolation is not specified
    # to protect the tests against some side-effects (not all
    # side-effects will be prevented)
    if isolation is Isolation.minimal:
        for dirpath, _, filenames in os.walk(dst):
            for filename in filenames:
                os.chmod(os.path.join(dirpath, filename), 0o444)


@pytest.fixture()
def app_params(
    request: pytest.FixtureRequest,
    test_params: TestParams,
    module_cache: ModuleCache,
    # the value of the fixtures below can be defined at the test file level
    sphinx_test_tempdir: Path,
    sphinx_builder: str,
    sphinx_isolation: IsolationPolicy | None,
    testroot_finder: TestRootFinder,
) -> AppParams:
    """Parameters that are specified by ``pytest.mark.sphinx``.

    See :class:`sphinx.testing.util.SphinxTestApp` for the allowed parameters.
    """
    if m := request.node.get_closest_marker('isolate'):
        # isolate() is equivalent to isolate('always')
        sphinx_isolation = m.args[0] if m.args else True

    shared_result_id = test_params['shared_result']
    args, kwargs = get_app_params(
        request.node,
        session_temp_dir=sphinx_test_tempdir,
        testroot_finder=testroot_finder,
        default_builder=sphinx_builder,
        default_isolation=sphinx_isolation,
        shared_result=shared_result_id,
    )
    assert shared_result_id == kwargs['shared_result']
    # restore the I/O stream values
    if shared_result_id and (frame := module_cache.restore(shared_result_id)):
        if kwargs.setdefault('status', frame['status']) is not frame['status']:
            pytest.fail('cannot use "shared_result" when "status" is explicitly given')
        if kwargs.setdefault('warning', frame['warning']) is not frame['warning']:
            pytest.fail('cannot use "shared_result" when "warning" is explicitly given')

    # copy the testroot files to the test sources directory
    _init_sources(kwargs['testroot_path'], kwargs['srcdir'], kwargs['isolate'])
    return AppParams(args, kwargs)


@pytest.fixture()
def test_params(request: pytest.FixtureRequest) -> TestParams:
    """Test parameters that are specified by ``pytest.mark.test_params``."""
    return get_test_params(request.node)


@pytest.fixture()
def app(
    app_params: AppParams,
    make_app: Callable[..., SphinxTestApp],
    module_cache: ModuleCache,
) -> Generator[SphinxTestApp, None, None]:
    """A :class:`sphinx.application.Sphinx` object suitable for testing."""
    # the 'app_params' fixture already depends on the 'test_result' fixture
    shared_result_id = app_params.kwargs['shared_result']
    app = make_app(*app_params.args, **app_params.kwargs)
    yield app

    if shared_result_id is not None:
        pass

    if shared_result_id is not None:
        module_cache.store(shared_result_id, app)


@pytest.fixture()
def status(app: SphinxTestApp) -> StringIO:
    """Fixture for the :func:`~sphinx.testing.fixtures.app` status stream."""
    return app.status


@pytest.fixture()
def warning(app: SphinxTestApp) -> StringIO:
    """Fixture for the :func:`~sphinx.testing.fixtures.app` warning stream."""
    return app.warning


@pytest.fixture()
def make_app(test_params: TestParams) -> Generator[Callable[..., SphinxTestApp], None, None]:
    """Fixture to create :class:`~sphinx.testing.util.SphinxTestApp` objects."""
    stack: list[SphinxTestApp] = []
    not_shared = test_params['shared_result'] is None

    def make(*args: Any, **kwargs: Any) -> SphinxTestApp:
        if not_shared:
            app = SphinxTestApp(*args, **kwargs)
        else:
            app = SphinxTestAppLazyBuild(*args, **kwargs)
        stack.append(app)
        return app

    syspath = sys.path.copy()
    yield make
    sys.path[:] = syspath

    while stack:
        stack.pop().cleanup()


_MODULE_CACHE_STASH_KEY: pytest.StashKey[ModuleCache] = pytest.StashKey()


@pytest.fixture()
def module_cache(request: pytest.FixtureRequest) -> ModuleCache:
    """A :class:`ModuleStorage` object."""
    module = find_context(request.node, 'module')
    return module.stash.setdefault(_MODULE_CACHE_STASH_KEY, ModuleCache())


@pytest.fixture(scope='module', autouse=True)
def _module_cache_clear(request: pytest.FixtureRequest) -> None:
    """Cleanup the shared result cache for the test module.

    This fixture is automatically invoked.
    """
    module = find_context(request.node, 'module')
    cache = module.stash.get(_MODULE_CACHE_STASH_KEY, None)
    if cache is not None:
        cache.clear()


@pytest.fixture()
def if_graphviz_found(app: SphinxTestApp) -> None:  # NoQA: PT004
    """Skip the test if the graphviz ``dot`` command is not found.

    Usage::

        @pytest.mark.usefixtures('if_graphviz_found')
        def test_if_dot_command_exists(): ...
    """
    graphviz_dot = getattr(app.config, 'graphviz_dot', '')
    try:
        if graphviz_dot:
            # print the graphviz_dot version, to check that the binary is available
            subprocess.run([graphviz_dot, '-V'], capture_output=True, check=False)
            return
    except OSError:  # No such file or directory
        pass

    pytest.skip('graphviz "dot" is not available')


@pytest.fixture()
def rollback_sysmodules() -> Generator[None, None, None]:  # NoQA: PT004
    """
    Rollback sys.modules to its value before testing to unload modules
    during tests.

    For example, used in test_ext_autosummary.py to permit unloading the
    target module to clear its cache.
    """
    # test setup
    sys_module_names = frozenset(sys.modules)
    # run the test
    yield
    # test teardown (in the reverse-order the modules are inserted)
    for name in reversed(list(sys.modules)):
        if name not in sys_module_names:
            del sys.modules[name]