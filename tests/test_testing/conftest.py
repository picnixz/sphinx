from __future__ import annotations

from pathlib import Path

import pytest

from .util import SPHINX_LIBDIR_PATH

SPHINX_PLUGIN_NAME = 'sphinx.testing.plugin'
DUMPER_PLUGIN_NAME = 'tests.test_testing.util.dumper'
pytest_plugins = [SPHINX_PLUGIN_NAME, 'pytester']
collect_ignore = [DUMPER_PLUGIN_NAME]


@pytest.fixture(autouse=True)
def pytester_conftest(pytester: pytest.Pytester) -> Path:
    testroot_dir = Path(__file__).parent.parent / 'roots'
    pytester.makepyprojecttoml(f'''
[pytest] 
pythonpath = {SPHINX_LIBDIR_PATH!r}
''')
    source = f'''
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, {SPHINX_LIBDIR_PATH!r})

import pytest

import sphinx.testing.plugin

import sphinx.locale

if TYPE_CHECKING:
    from collections.abc import Generator

def _init_console(locale_dir=sphinx.locale._LOCALE_DIR, catalog='sphinx'):
    return sphinx.locale.NullTranslations(), False

sphinx.locale.init_console = _init_console


# 'xdist' will be added on demand when invoking pytester
pytest_plugins = [{DUMPER_PLUGIN_NAME!r}]
collect_ignore = [{DUMPER_PLUGIN_NAME!r}]

@pytest.fixture(scope='session')
def default_testroot(request: pytest.FixtureRequest) -> str:
    return getattr(request, 'param', 'minimal')

@pytest.fixture(scope='session')
def testroot_prefix(request: pytest.FixtureRequest) -> str:
    return getattr(request, 'param', 'test-')

@pytest.fixture(scope='session')
def rootdir() -> Path:
    return Path('{testroot_dir!s}')
'''
    return pytester.makeconftest(source)
