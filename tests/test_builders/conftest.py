from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from sphinx.testing.util import etree_html_parse

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path

    from xml.etree.ElementTree import ElementTree

etree_cache: dict[Path, ElementTree] = {}


def _etree_parse(source: Path) -> ElementTree:
    if source in etree_cache:
        return etree_cache[source]

    # do not use etree_cache.setdefault() to avoid calling xml.html.parse()
    etree_cache[source] = tree = etree_html_parse(source)
    return tree


@pytest.fixture(scope='package')
def cached_etree_parse() -> Generator[Callable[[Path], ElementTree], None, None]:
    """Provide caching for :func:`sphinx.testing.util.etree_html_parse`."""
    yield _etree_parse
    etree_cache.clear()
