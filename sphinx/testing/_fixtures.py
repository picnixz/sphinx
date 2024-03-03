"""Private utililty functions for :mod:`sphinx.testing.plugin`.

This module is an implementation detail and any provided function
or class can be altered, removed or moved without prior notice.
"""

from __future__ import annotations

__all__ = ()

import binascii
import json
import os
import pickle
import uuid
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, TypedDict, cast

import pytest

from sphinx.testing._isolation import Isolation, parse_isolation
from sphinx.testing.pytest_util import (
    _mark_fail,
    check_mark_keywords,
    get_mark_parameters,
    get_node_location,
)

if TYPE_CHECKING:
    from io import StringIO
    from typing import Any

    from _pytest.nodes import Node as PytestNode
    from typing_extensions import Required

    from sphinx.testing._isolation import IsolationPolicy
    from sphinx.testing.pytest_util import TestNodeLocation, TestRootFinder


class SphinxMarkEnviron(TypedDict, total=False):
    """Typed dictionary for the arguments of :func:`pytest.mark.sphinx`.

    Note that this class differs from :class:`SphinxInitKwargs` since it
    reflects the signature of the :func:`pytest.mark.sphinx` marker, but
    not of the :class:`~sphinx.testing.util.SphinxTestApp` constructor.
    """

    buildername: str
    confoverrides: dict[str, Any]
    warningiserror: bool
    tags: list[str]
    verbosity: int
    parallel: int
    keep_going: bool
    docutils_conf: str

    # added or updated fields
    testroot: str | None
    isolate: IsolationPolicy | None


class SphinxInitKwargs(TypedDict, total=False):
    """The type of the keyword arguments after processing.

    Such objects are constructed from :class:`SphinxMarkEnviron` objects.
    """

    # :class:`sphinx.application.Sphinx` positional arguments as keywords
    buildername: Required[str]
    """The deduced builder name."""
    # :class:`sphinx.application.Sphinx` required arguments
    srcdir: Required[Path]
    """Absolute path to the test sources directory.

    The uniqueness of this path depends on the isolation policy,
    the location of the test and the application's configuration.
    """
    # :class:`sphinx.application.Sphinx` optional arguments
    confoverrides: dict[str, Any] | None
    status: StringIO | None
    warning: StringIO | None
    freshenv: bool
    warningiserror: bool
    tags: list[str] | None
    verbosity: int
    parallel: int
    keep_going: bool
    # :class:`sphinx.testing.util.SphinxTestApp` optional arguments
    docutils_conf: str | None
    builddir: Path | None
    # :class:`sphinx.testing.util.SphinxTestApp` extras arguments
    isolate: Required[Isolation]
    """The deduced isolation policy."""
    testroot: Required[str | None]
    """The deduced testroot ID (possibly None if the default ID is not set)."""
    testroot_path: Required[str | None]
    """The absolute path to the testroot directory, if any."""
    shared_result: Required[str | None]
    """The optional shared result ID."""


class AppParams(NamedTuple):
    """The processed arguments of :func:`pytest.mark.sphinx`.

    The *args* and *kwargs* values can be directly used as inputs
    to the :class:`~sphinx.testing.util.SphinxTestApp` constructor.
    """

    args: list[Any]
    """The constructor positional arguments, except ``buildername``."""
    kwargs: SphinxInitKwargs
    """The constructor keyword arguments, including ``buildername``."""


class TestParams(TypedDict):
    """A view on the arguments of :func:`pytest.mark.test_params`."""

    shared_result: str | None


def _get_sphinx_environ(node: PytestNode, default_builder: str) -> SphinxMarkEnviron:
    args, kwargs = get_mark_parameters(node, 'sphinx')

    if len(args) > 1:
        _mark_fail('sphinx', 'expecting at most one positional argument')

    env = cast(SphinxMarkEnviron, kwargs)
    if env.pop('buildername', None) is not None:
        _mark_fail('sphinx', '%r is a positional-only argument' % 'buildername')
    env['buildername'] = buildername = args[0] if args else default_builder

    if not buildername:
        _mark_fail('sphinx', 'invalid builder name: %r' % buildername)

    check_mark_keywords('sphinx', SphinxMarkEnviron.__annotations__, env, node=node)
    return env


def _get_test_srcdir(testroot: str | None, shared_result: str | None) -> str:
    """Deduce the sources directory from the given arguments.

    :param testroot: An optional testroot ID to use.
    :param shared_result: An optional shared result ID.
    :return: The sources directory name *srcdir* (non-empty string).
    """
    check_mark_str_args('sphinx', testroot=testroot)
    check_mark_str_args('test_params', shared_result=shared_result)

    if shared_result is not None:
        # include the testroot id for visual purposes (unless it is
        # not specified, which only occurs when there is no rootdir
        # at all)
        return f'{testroot}-{shared_result}' if testroot else shared_result

    if testroot is None:  # neither an explicit nor the default testroot ID is given
        pytest.fail('missing %r or %r parameter' % ('testroot', 'srcdir'))
    return testroot


def process_sphinx(
    node: PytestNode,
    session_temp_dir: str | os.PathLike[str],
    testroot_finder: TestRootFinder,
    default_builder: str,
    default_isolation: IsolationPolicy | None,
    shared_result: str | None,
) -> tuple[list[Any], SphinxInitKwargs]:
    """Process the :func:`pytest.mark.sphinx` marker.

    :param node: The pytest node to parse.
    :param session_temp_dir: The session temporary directory.
    :param testroot_finder: The testroot finder object.
    :param default_builder: The application default builder name.
    :param default_isolation: The isolation default policy.
    :param shared_result: An optional shared result ID.
    :return: The application positional and keyword arguments.
    """
    # 1. process pytest.mark.sphinx
    env = _get_sphinx_environ(node, default_builder)
    # 1.1. deduce the isolation policy
    isolation = env.setdefault('isolate', default_isolation)
    isolation = env['isolate'] = parse_isolation(isolation)
    # 1.2. deduce the testroot ID
    testroot_id = env['testroot'] = env.get('testroot', testroot_finder.default)
    # 1.3. deduce the srcdir ID
    srcdir = _get_test_srcdir(testroot_id, shared_result)

    # 2. process the srcdir ID according to the isolation policy
    if isolation is Isolation.always:
        srcdir = unique_source_id(srcdir)
    elif isolation is Isolation.grouped:
        if (location := get_node_location(node)) is None:
            srcdir = unique_source_id(srcdir)
        else:
            # in the case of a 'grouped' isolation, we want
            # to keep the same 'srcdir_id' but add some UID
            # based on the node location ID
            location_id = node_location_id(location)
            srcdir = f'{srcdir}-{location_id}'

    # Do a somewhat hash on configuration values to give a minimal protection
    # against side-effects (two tests with the same configuration should have
    # the same output; if they mess up with their sources directory, then they
    # should be isolated accordingly). If there is a bug in the test suite, we
    # can reduce the number of tests that can have dependencies by adding some
    # isolation safeguards.
    namespace = get_namespace_id(node)
    env_crc32 = 0 if isolation is Isolation.always else get_environ_checksum(
        env['buildername'],
        # The default values must be kept in sync with the constructor
        # default values of :class:`sphinx.testing.util.SphinxTestApp`.
        env.get('confoverrides'),
        env.get('freshenv', False),
        env.get('warningiserror', False),
        env.get('tags'),
        env.get('verbosity', 0),
        env.get('parallel', 0),
        env.get('keep_going', False),
    )

    kwargs = cast(SphinxInitKwargs, env)
    kwargs['srcdir'] = Path(session_temp_dir, namespace, str(env_crc32), srcdir)
    kwargs['testroot_path'] = testroot_finder.find(testroot_id)
    kwargs['shared_result'] = shared_result
    return [], kwargs


def process_test_params(node: PytestNode) -> TestParams:
    """Process the :func:`pytest.mark.test_params` marker.

    :param node: The pytest node to parse.
    :return: The desired keyword arguments.
    """
    ret = TestParams(shared_result=None)
    if (m := node.get_closest_marker('test_params')) is None:
        return ret

    if m.args:
        _mark_fail('test_params', 'unexpected positional argument')

    check_mark_keywords(
        'test_params', TestParams.__annotations__,
        kwargs := m.kwargs, node=node, strict=True,
    )

    if (shared_result_id := kwargs.get('shared_result', None)) is None:
        # generate a random shared_result for @pytest.mark.test_params()
        # based on either the location of node (so that it is the same
        # when using @pytest.mark.parametrize())
        if (location := get_node_location(node)) is None:
            shared_result_id = unique_source_id()
        else:
            shared_result_id = node_location_id(location)

    ret['shared_result'] = shared_result_id
    return ret


def process_isolate(
    node: PytestNode, default: IsolationPolicy | None,
) -> IsolationPolicy | None:
    """Process the :func:`pytest.mark.isolate` marker.

    :param node: The pytest node to parse.
    :param default: The default isolation policy given by an external fixture.
    :return: The isolation policy given by the marker.
    """
    # try to find an isolation policy from the 'isolate' marker
    if m := node.get_closest_marker('isolate'):
        # do not allow keyword arguments
        check_mark_keywords('isolate', [], m.kwargs, node=node, strict=True)
        if not m.args:
            # isolate() is equivalent to isolate('always')
            return Isolation.always

        if len(m.args) == 1:
            return parse_isolation(m.args[0])

        _mark_fail('isolate', 'expecting at most one positional argument')
    return default


def check_mark_str_args(mark: str, /, **kwargs: Any) -> None:
    """Check that marker string arguments are either None or non-empty.

    :param mark: The marker name.
    :param kwargs: A mapping of marker argument names and their values.
    :raise pytest.Failed: The validation failed.
    """
    for argname, value in kwargs.items():
        if value and not isinstance(value, str) or not value and value is not None:
            msg = "expecting a non-empty string or None for %r, got: %r"
            _mark_fail(mark, msg % (argname, value))


def get_environ_checksum(*args: Any) -> int:
    """Compute a CRC-32 checksum of *args*."""
    def default_encoder(x: object) -> str:
        try:
            return pickle.dumps(x, protocol=pickle.HIGHEST_PROTOCOL).hex()
        except (NotImplementedError, TypeError, ValueError):
            return hex(id(x))[2:]

    # use the most compact JSON format
    env = json.dumps(args, ensure_ascii=False, sort_keys=True, indent=None,
                     separators=(',', ':'), default=default_encoder)
    # avoid using unique_object_id() since we do not really need SHA-1 entropy
    return binascii.crc32(env.encode('utf-8', errors='backslashreplace'))


def node_location_id(location: TestNodeLocation) -> str:
    """Make a unique ID out of a test node location."""
    fspath, lineno = location
    return unique_object_id(f'{fspath}L{lineno}')


def get_namespace_id(node: PytestNode) -> str:
    """Get a unique hexadecimal identifier for the node's namespace.

    The node's namespace is defined by all the modules and classes
    the node is part of.
    """
    namespace = '@'.join(filter(None, (
        t.obj.__name__ or None for t in node.listchain()
        if isinstance(t, (pytest.Module, pytest.Class)) and t.obj
    ))) or node.nodeid
    return unique_object_id(namespace)


# Use a LRU cache to speed-up the generation of the UUID-5 value
# when generating the object ID for parametrized sub-tests (those
# sub-tests will be using the same "object id") since UUID-5 is
# based on SHA-1.
@lru_cache(maxsize=65536)
def unique_object_id(name: str) -> str:
    """Get a unique hexadecimal identifier for an object name.

    :param name: The name of the object to get a unique ID of.
    :return: A unique hexadecimal identifier for *name*.
    """
    # ensure that non UTF-8 characters are supported and handled similarly
    sanitized = name.encode('utf-8', errors='backslashreplace').decode('utf-8')
    return uuid.uuid5(uuid.NAMESPACE_OID, sanitized).hex


def unique_source_id(prefix: str | os.PathLike[str] | None = None) -> str:
    r"""Generate a unique identifier prefixed by *prefix*.

    :param prefix: An optional prefix to prepend to the unique identifier.
    :return: A unique identifier.

    .. note:: The probability for generating two identical IDs is negligible
              for a security parameter :math:`\lambda = 128`.
    """
    # We can be extremely unlucky (or lucky) to have collisions on UUIDs
    # but for the sake of efficiency (and since there are no real security
    # concerns in Sphinx), we can live with 128-bit AES equivalent security.
    suffix = uuid.uuid4().hex
    return '-'.join((os.fsdecode(prefix), suffix)) if prefix else suffix
