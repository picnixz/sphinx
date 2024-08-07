import os
import sys

sys.path.insert(0, os.path.abspath('.'))

extensions = ['sphinx.ext.autodoc', 'sphinx.ext.coverage']

coverage_modules = [
    'grog',
]
coverage_ignore_pyobjects = [
    r'^grog\.coverage_ignored(\..*)?$',
    r'\.Ignored$',
    r'\.Documented\.ignored\d$',
]
