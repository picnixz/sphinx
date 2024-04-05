"""Private utility functions for :mod:`sphinx.testing.matcher`.

All objects provided by this module are considered an implementation detail
and are not meant to be used by external libraries.
"""

from __future__ import annotations

__all__ = ()

import fnmatch
import re
from collections.abc import Set
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from sphinx.testing.matcher._util import BlockPattern, LinePattern, PatternLike
    from sphinx.testing.matcher.options import Flavor


def _check_flavor(flavor: Flavor) -> None:
    allowed: Sequence[Flavor] = ('none', 'fnmatch', 're')
    if flavor not in allowed:
        msg = f'unknown flavor: {flavor!r} (choose from: {allowed})'
        raise ValueError(msg)


def _sort_pattern(s: PatternLike) -> tuple[str, int, int]:
    if isinstance(s, str):
        return (s, -1, -1)
    return (s.pattern, s.flags, s.groups)


@overload
def to_line_patterns(line: str, /) -> tuple[str]: ...  # NoQA: E704
@overload
def to_line_patterns(pattern: re.Pattern[str], /) -> tuple[re.Pattern[str]]: ...  # NoQA: E704
@overload  # NoqA: E302
def to_line_patterns(  # NoQA: E704
    patterns: Set[LinePattern] | Sequence[LinePattern], /
) -> tuple[LinePattern, ...]: ...
def to_line_patterns(  # NoqA: E302
    patterns: LinePattern | Set[LinePattern] | Sequence[LinePattern], /
) -> Sequence[LinePattern]:
    """Get a read-only sequence of line-matching patterns.

    :param patterns: One or more patterns a line should match (in its entirety).
    :return: The possible line patterns.

    By convention,::

        to_line_patterns("my pattern") == to_line_patterns(["my pattern"])

    .. note::

       If *expect* is a :class:`~collections.abc.Set`-like object, the order
       of the output sequence is an implementation detail but guaranteed to
       be the same for the same inputs. Otherwise, the order of *expect* is
       retained, in case this could make a difference.
    """
    if isinstance(patterns, (str, re.Pattern)):
        return (patterns,)
    if isinstance(patterns, Set):
        return tuple(sorted(patterns, key=_sort_pattern))
    return tuple(patterns)


@overload
def to_block_pattern(pattern: str, /) -> tuple[str, ...]: ...  # NoQA: E704
@overload
def to_block_pattern(pattern: re.Pattern[str], /) -> tuple[re.Pattern[str]]: ...  # NoQA: E704
@overload
def to_block_pattern(patterns: BlockPattern, /) -> BlockPattern: ...  # NoQA: E704
def to_block_pattern(patterns: PatternLike | BlockPattern, /) -> BlockPattern:  # NoQA: E302
    r"""Get a read-only sequence for a s single block pattern.

    :param patterns: A string, :class:`~re.Pattern` or a sequence thereof.
    :return: The line patterns of the block.

    When *expect* is a single string, it is split into lines to produce
    the corresponding block pattern, e.g.::

        to_block_pattern('line1\nline2') == ('line1', 'line2')
    """
    if isinstance(patterns, str):
        return tuple(patterns.splitlines())
    if isinstance(patterns, re.Pattern):
        return (patterns,)
    return tuple(patterns)


@overload
def format_expression(fn: Callable[[str], str], x: str, /) -> str: ...  # NoQA: E704
@overload
def format_expression(fn: Callable[[str], str], x: re.Pattern[str], /) -> re.Pattern[str]: ...  # NoQA: E704
def format_expression(fn: Callable[[str], str], x: PatternLike, /) -> PatternLike:  # NoQA: E302
    """Transform regular expressions, leaving compiled patterns untouched."""
    return fn(x) if isinstance(x, str) else x


def string_expression(line: str, /) -> str:
    """A regular expression matching exactly *line*."""
    # use '\A' and '\Z' to match the beginning and end of the string
    return rf'\A{re.escape(line)}\Z'


def translate(
    patterns: Iterable[PatternLike],
    *,
    flavor: Flavor,
    escape: Callable[[str], str] | None = string_expression,
    str2regexpr: Callable[[str], str] | None = None,
    str2fnmatch: Callable[[str], str] | None = fnmatch.translate,
) -> Iterable[PatternLike]:
    r"""Translate regular expressions according to *flavor*.

    Non-compiled regular expressions are translated by the translation function
    corresponding to the given *flavor* while compiled patterns are kept as is.

    :param patterns: An iterable of regular expressions to translate.
    :param flavor: The translation flavor for non-compiled patterns.
    :param escape: Translation function for ``'none'`` flavor.
    :param str2regexpr: Translation function for ``'re'`` flavor.
    :param str2fnmatch: Translation function for ``'fnmatch'`` flavor.
    :return: An iterable of :class:`re`-style pattern-like objects.
    """
    _check_flavor(flavor)

    if flavor == 'none' and callable(translator := escape):
        return (format_expression(translator, expr) for expr in patterns)

    if flavor == 're' and callable(translator := str2regexpr):
        return (format_expression(translator, expr) for expr in patterns)

    if flavor == 'fnmatch' and callable(translator := str2fnmatch):
        return (format_expression(translator, expr) for expr in patterns)

    return patterns


def compile(
    patterns: Iterable[PatternLike],
    *,
    flavor: Flavor,
    escape: Callable[[str], str] | None = string_expression,
    str2regexpr: Callable[[str], str] | None = None,
    str2fnmatch: Callable[[str], str] | None = fnmatch.translate,
) -> Sequence[re.Pattern[str]]:
    """Compile one or more patterns into :class:`~re.Pattern` objects.

    :param patterns: An iterable of patterns to translate and compile.
    :param flavor: The translation flavor for non-compiled patterns.
    :param escape: Translation function for ``'none'`` flavor.
    :param str2regexpr: Translation function for ``'re'`` flavor.
    :param str2fnmatch: Translation function for ``'fnmatch'`` flavor.
    :return: A sequence of compiled regular expressions.
    """
    patterns = translate(
        patterns,
        flavor=flavor,
        escape=escape,
        str2regexpr=str2regexpr,
        str2fnmatch=str2fnmatch,
    )
    # mypy does not like map + re.compile() although it is correct but
    # this is likely due to https://github.com/python/mypy/issues/11880
    return tuple(re.compile(pattern) for pattern in patterns)
