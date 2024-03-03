from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _pytest.pytester import Pytester

DUMPER_PLUGIN_NAME = 'tests.test_testing.util.dumper'
pytest_plugins = ['pytester', 'xdist']
collect_ignore = [DUMPER_PLUGIN_NAME]


@pytest.fixture(autouse=True)
def pytester_source(pytester: Pytester, pytestconfig: pytest.Config) -> Path:
    testroot_dir = Path(__file__).parent.parent / 'roots'
    source = f'''
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import os
import pytest

import sphinx.locale

if TYPE_CHECKING:
    from collections.abc import Generator

def _init_console(locale_dir=sphinx.locale._LOCALE_DIR, catalog='sphinx'):
    return sphinx.locale.NullTranslations(), False

sphinx.locale.init_console = _init_console

# ensure that the sub-terminal spawned by ``pytester``
# inherits the width of the terminal running ``pytest``
os.environ['COLUMNS'] = '{shutil.get_terminal_size()[0]}'

# 'xdist' will be added on demand when invoking pytester
pytest_plugins = ['sphinx.testing.plugin', {DUMPER_PLUGIN_NAME!r}]
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
