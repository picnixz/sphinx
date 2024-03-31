from __future__ import annotations

__all__ = ('Options', 'get_option')

from typing import TYPE_CHECKING, TypedDict, final, overload

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import Final, Literal, TypeVar, Union

    from sphinx.testing._matcher.util import LinePattern

    FlagOption = Literal['color', 'ctrl', 'keepends', 'empty', 'compress', 'unique']

    StripOption = Literal['strip', 'stripline']
    StripChars = Union[bool, str, None]

    DeleteOption = Literal['delete']
    DeletePattern = Union[LinePattern, Sequence[LinePattern]]

    FilteringOption = Literal['ignore']
    LinePredicate = Callable[[str], object]

    FlavorOption = Literal['flavor']
    Flavor = Literal['re', 'fnmatch', 'exact']

    # For some reason, mypy does not like Union of Literal,
    # so we wrap the Literal types inside a bigger Literal.
    OptionName = Literal[FlagOption, StripOption, DeleteOption, FilteringOption, FlavorOption]

    DT = TypeVar('DT')


@final
class Options(TypedDict, total=False):
    """Options for a :class:`~sphinx.testing.matcher.LineMatcher` object.

    Some options directly act on the original string (e.g., :attr:`strip`),
    while others (e.g., :attr:`stripline`) act on the lines obtained after
    splitting the (transformed) original string.
    """

    color: bool
    """Indicate whether to keep the ANSI escape sequences for colors.

    The default value is ``False``.
    """

    ctrl: bool
    """Indicate whether to keep the non-color ANSI escape sequences.

    The default value is ``True``.
    """

    strip: StripChars
    """Call :meth:`str.strip` on the original source.

    The allowed values for :attr:`strip` are:

    * ``True`` -- remove leading and trailing whitespaces (the default).
    * ``False`` -- keep leading and trailing whitespaces.
    * a string (*chars*) -- remove leading and trailing characters in *chars*.
    """

    stripline: StripChars
    """Call :meth:`str.strip` on the lines obtained after splitting the source.

    The allowed values for :attr:`strip` are:

    * ``True`` -- remove leading and trailing whitespaces.
    * ``False`` -- keep leading and trailing whitespaces (the default).
    * a string (*chars*) -- remove leading and trailing characters in *chars*.
    """

    keepends: bool
    """If true, keep line breaks in the output.

    The default value is ``False``.
    """

    empty: bool
    """If true, keep empty lines in the output.

    The default value is ``True``.
    """

    compress: bool
    """Eliminate duplicated consecutive lines in the output.

    The default value is ``False``.

    For instance, ``['a', 'b', 'b', 'c'] -> ['a', 'b', 'c']``.

    Note that if :attr:`empty` is ``False``, empty lines are removed *before*
    the duplicated lines, i.e., ``['a', 'b', '', 'b'] -> ['a', 'b']``.
    """

    unique: bool
    """Eliminate multiple occurrences of lines in the output.

    The default value is ``False``.

    This option is only applied at the very end of the transformation chain,
    after empty and duplicated consecutive lines might have been eliminated.
    """

    delete: DeletePattern
    """Strings or patterns to remove from the beginning of the line.
    
    When :attr:`delete` is a single string, it is considered as a
    prefix to remove from the output lines.

    When :attr:`delete` is a single pattern, each line removes the
    matching groups.
    
    When :attr:`delete` consists of one or more elements, either
    a string or a :class:`~re.Pattern` objects, then all matching
    groups and prefixes are removed until none remains.

    This transformation is applied at the end of the transformation 
    chain, just before filtering the output lines are filtered with 
    the :attr:`ignore` predicate
    """

    ignore: LinePredicate | None
    """A predicate for filtering the output lines.

    Lines that satisfy this predicate are not included in the output.
    
    The default is ``None``, meaning that all lines are included.
    """

    flavor: Flavor
    """Indicate how strings are matched against non-compiled patterns.

    The allowed values for :attr:`flavor` are:

    * ``'exact'`` -- match lines using string equality (the default).
    * ``'fnmatch'`` -- match lines using :mod:`fnmatch`-style patterns.
    * ``'re'`` -- match lines using :mod:`re`-style patterns.

    This option only affects non-compiled patterns (i.e., those given
    as :class:`str` and not :class:`~re.Pattern` objects).
    """


@final
class CompleteOptions(TypedDict):
    """Same as :class:`Options` but as a total dictionary."""

    # Whenever a new option in :class:`Options` is added, do not
    # forget to add it here and in :data:`DEFAULT_OPTIONS`.

    color: bool
    ctrl: bool

    strip: StripChars
    stripline: StripChars

    keepends: bool
    empty: bool
    compress: bool
    unique: bool

    delete: DeletePattern
    ignore: LinePredicate | None

    flavor: Flavor


DEFAULT_OPTIONS: Final[CompleteOptions] = CompleteOptions(
    color=False,
    ctrl=True,
    strip=True,
    stripline=False,
    keepends=False,
    empty=True,
    compress=False,
    unique=False,
    delete=(),
    ignore=None,
    flavor='exact',
)
"""The default (read-only) options values."""

if TYPE_CHECKING:
    _OptionsView = Union[Options, CompleteOptions]


# Disable the ruff formatter to minimize the number of empty lines.
#
# When an option is added, add an overloaded definition
# so that mypy can correctly deduce the option's type.
#
# fmt: off
# boolean-like options
@overload
def get_option(options: _OptionsView, name: FlagOption, /) -> bool: ...  # NoQA: E704
@overload
def get_option(options: _OptionsView, name: FlagOption, default: DT, /) -> bool | DT: ...  # NoQA: E704
# strip-like options
@overload
def get_option(options: _OptionsView, name: StripOption, /) -> StripChars: ...  # NoQA: E704
@overload
def get_option(options: _OptionsView, name: StripOption, default: DT, /) -> StripChars | DT: ...  # NoQA: E501, E704
# delete prefix/suffix option
@overload
def get_option(options: _OptionsView, name: DeleteOption, /) -> DeletePattern: ...  # NoQA: E704
@overload
def get_option(options: _OptionsView, name: DeleteOption, default: DT, /) -> DeletePattern | DT: ...  # NoQA: E501, E704
# filtering options
@overload
def get_option(options: _OptionsView, name: FilteringOption, /) -> LinePredicate | None: ...  # NoQA: E704
@overload
def get_option(options: _OptionsView, name: FilteringOption, default: DT, /) -> LinePredicate | None | DT: ...  # NoQA: E501, E704
# miscellaneous options
@overload
def get_option(options: _OptionsView, name: FlavorOption, /) -> Flavor: ...  # NoQA: E704
@overload
def get_option(options: _OptionsView, name: FlavorOption, default: DT, /) -> Flavor | DT: ...  # NoQA: E704
# fmt: on
def get_option(options: _OptionsView, name: OptionName, /, *default: DT) -> object | DT:  # NoQA: E302
    if name in options:
        return options[name]
    return default[0] if default else DEFAULT_OPTIONS[name]
