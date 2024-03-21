from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

import xml.etree
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import ElementTree, tostring as etree_tostring

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


def _get_text(node: Element) -> str:
    if node.text is not None:
        # the node has only one text
        return node.text

    # the node has tags and text; gather texts just under the node
    return ''.join(n.tail or '' for n in node)


def check_xpath(
    etree: ElementTree,
    fname: str | os.PathLike[str],
    xpath: str,
    check: str | re.Pattern[str] | Callable[[Sequence[Element]], None] | None,
    be_found: bool = True,
) -> None:
    assert isinstance(etree, ElementTree)

    nodes = list(etree.findall(xpath))
    assert all(isinstance(node, Element) for node in nodes)

    if check is None:
        assert nodes == [], ('found any nodes matching xpath '
                             f'{xpath!r} in file {os.fsdecode(fname)}')
        return
    else:
        assert nodes != [], ('did not find any node matching xpath '
                             f'{xpath!r} in file {os.fsdecode(fname)}')
    if callable(check):
        check(nodes)
    elif not check:
        # only check for node presence
        pass
    else:
        rex = re.compile(check)
        if be_found:
            if any(rex.search(_get_text(node)) for node in nodes):
                return
        else:
            if all(not rex.search(_get_text(node)) for node in nodes):
                return

        context = list(map(etree_tostring, nodes))
        msg = (f'{check!r} not found in any node matching '
               f'{xpath!r} in file {os.fsdecode(fname)}: {context}')
        raise AssertionError(msg)
