"""Implementation of xdist hooks."""

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest
    from execnet import XSpec


def pytest_xdist_setupnodes(config: pytest.Config, specs: list[XSpec]) -> None:
    assert config.pluginmanager.has_plugin('xdist'), 'xdist is not loaded'
    assert not hasattr(config, 'workerinput'), 'hook must be invoked in the controller node'

    # ensure that the workers inherit the same terminal size
    size = shutil.get_terminal_size()
    columns = str(size.columns)
    columns = os.environ.setdefault('COLUMNS', columns)

    for spec in specs:
        spec.env['COLUMNS'] = columns
