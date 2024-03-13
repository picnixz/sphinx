"""Facade for a unified API."""

from __future__ import annotations

__all__ = ()

from functools import singledispatch
from typing import TYPE_CHECKING, TypeVar, overload

from _pytest.config import Config
from _pytest.fixtures import FixtureRequest
from _pytest.nodes import Node as PytestNode
from _pytest.tmpdir import TempPathFactory

if TYPE_CHECKING:
    from typing import Any

    from _pytest.stash import Stash


###############################################################################
# _pytest.config.Config accessor
###############################################################################

def get_config(subject: Config | FixtureRequest | PytestNode, /) -> Config:
    """Get the underlying pytest configuration of the *subject*."""
    if isinstance(subject, Config):
        return subject

    config = getattr(subject, 'config', None)
    if config is None or not isinstance(config, Config):
        msg = f'no configuration accessor for {type(subject)} objects'
        raise TypeError(msg)
    return config


###############################################################################
# _pytest.tempdir.TempPathFactory accessor
###############################################################################

_DT = TypeVar('_DT')


# fmt: off
@overload
def get_tmp_path_factory(subject: Any, /) -> TempPathFactory: ...  # NoQA: E704
@overload
def get_tmp_path_factory(subject: Any, default: _DT, /) -> TempPathFactory | _DT: ...  # NoQA: E501, E704
# fmt: on
def get_tmp_path_factory(subject: Any, /, *default: Any) -> Any:  # NoQA: E302
    """Get the optional underlying path factory of the *subject*."""
    config = get_config(subject)
    factory = getattr(config, '_tmp_path_factory', None)
    if factory is None:
        if default:
            return default[0]

        msg = f'cannot extract the underlying temporary path factory from {subject!r}'
        raise AttributeError(msg)
    assert isinstance(factory, TempPathFactory)
    return factory


###############################################################################
# _pytest.stash.Stash accessor
###############################################################################


@singledispatch
def get_stash(subject: Any, /) -> Stash:
    """Get the underlying stash of the *subject*.

    This accessor is needed for mypy since sometimes the stash is not typed.
    """
    msg = f'no stash extractor for objects of type: {type(subject)}'
    raise TypeError(msg)


@get_stash.register(PytestNode)
def _(node: PytestNode, /) -> Stash:
    return node.stash


@get_stash.register(FixtureRequest)
def _(request: FixtureRequest, /) -> Stash:
    return request.node.stash
