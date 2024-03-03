"""Private utilities for the `pytest-xdist`_ plugin.

.. _pytest-xdist: https://pytest-xdist.readthedocs.io

All functions in this module have an undefined behaviour if they are
called before the ``pytest_cmdline_main`` hook.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import pytest

from sphinx.testing.pytest_util import get_mark_parameters

if TYPE_CHECKING:
    from _pytest.nodes import Node as PytestNode

#: Scheduling policy for :mod:`xdist` specified by :option:`!--dist`.
Policy = Literal['no', 'each', 'load', 'loadscope', 'loadfile', 'loadgroup', 'worksteal']


def get_xdist_policy(config: pytest.Config) -> Policy:
    """Get the ``config.option.dist`` value even if :mod:`!xdist` is absent.

    Use ``get_xdist_policy(config) != 'no'`` to determine whether the plugin
    is active and loaded or not.

    On systems without the :mod:`!xdist` module, the ``dist`` option does
    not even exist in the first place and thus using ``config.option.dist``
    would raise an :exc:`AttributeError`.
    """
    if config.pluginmanager.has_plugin('xdist'):
        return config.option.dist
    return 'no'


def is_pytest_xdist_enabled(config: pytest.Config) -> bool:
    """Check that the :mod:`!xdist` plugin is loaded and active.

    :param config: A pytest configuration object.
    """
    return get_xdist_policy(config) != 'no'


def is_pytest_xdist_controller(config: pytest.Config) -> bool:
    """Check if the configuration is attached to the xdist controller.

    If the :mod:`!xdist` plugin is not active, this returns ``False``.

    .. important::

       This function differs from :func:`xdist.is_xdist_worker` in the
       sense that it works even if the :mod:`xdist` plugin is inactive.
    """
    return is_pytest_xdist_enabled(config) and not is_pytest_xdist_worker(config)


def is_pytest_xdist_worker(config: pytest.Config) -> bool:
    """Check if the configuration is attached to a xdist worker.

    If the :mod:`!xdist` plugin is not active, this returns ``False``.

    .. important::

       This function differs from :func:`xdist.is_xdist_controller` in the
       sense that it works even if the :mod:`xdist` plugin is inactive.
    """
    return is_pytest_xdist_enabled(config) and hasattr(config, 'workerinput')


def get_pytest_xdist_group(node: PytestNode, default: str = 'default', /) -> str | None:
    """Get the :func:`!pytest.mark.xdist_group` of a *node*, if any.

    :param node: The pytest node to parse.
    :param default: The default group if the marker has no argument.
    :return: The group name or ``None`` when :mod:`!xdist` is inactive.
    """
    if (
        not is_pytest_xdist_enabled(node.config)
        or node.get_closest_marker('xdist_group') is None
    ):
        return None

    args, kwargs = get_mark_parameters(node, 'xdist_group')
    return args[0] if args else kwargs.get('name', default)


def set_pytest_xdist_group(node: PytestNode, group: str, /, *, append: bool = True) -> None:
    """Add a ``@pytest.mark.xdist_group(group)`` to *node*.

    This is a no-op if :mod:`!xdist` is inactive.
    """
    if is_pytest_xdist_enabled(node.config):
        node.add_marker(pytest.mark.xdist_group(group), append=append)
