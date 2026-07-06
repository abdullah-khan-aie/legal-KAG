# ruff: noqa  (vendored from openspg-kag; local fix: recursion guard, see below)
# -*- coding: utf-8 -*-

import importlib
import logging
import os
import pkgutil
import sys
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)

# Directories already walked by ``import_modules_from_path``. The walker imports
# subpackages by leaf name against a ``sys.path`` it keeps prepending to, so a
# nested package (e.g. ``common``) can resolve to an already-imported same-named
# package (``kag/common``) and recurse without bound. Deduping by absolute path
# makes each directory be processed exactly once, which is also all that's needed
# for @register side effects.
_IMPORTED_PATHS: set = set()


def append_python_path(path: Union[os.PathLike, str]) -> None:
    """
    Append the given path to `sys.path`.
    """
    # In some environments, such as TC, it fails when sys.path contains a relative path, such as ".".
    path = Path(path).resolve()
    path = str(path)
    sys.path.insert(0, path)


def import_modules_from_path(path: str) -> None:
    """
    Import every submodule under the given package directory so their
    ``@register`` side effects run.

    Submodules are imported by their fully-qualified name (``pkgutil.walk_packages``
    with a ``prefix``) rather than by bare leaf name. This matters because the
    tree has same-named subpackages under different parents -- e.g.
    ``builder/prompt`` and ``solver/prompt``. The previous leaf-name scheme
    imported the first ``prompt`` as top-level ``prompt``, cached it in
    ``sys.modules``, and then silently skipped every other ``prompt`` package,
    so those modules never registered. Fully-qualified names keep them distinct.
    """
    abspath = os.path.abspath(os.path.normpath(path))
    if abspath in _IMPORTED_PATHS:
        return
    _IMPORTED_PATHS.add(abspath)
    importlib.invalidate_caches()

    module_path, package_name = os.path.split(abspath)
    append_python_path(module_path)
    package = importlib.import_module(package_name)
    search_paths = list(getattr(package, "__path__", []))
    if not search_paths:
        return

    def _onerror(name: str) -> None:
        logger.warning("registry walk: could not import package %s", name)

    for _finder, name, _is_pkg in pkgutil.walk_packages(
        search_paths, prefix=package_name + ".", onerror=_onerror
    ):
        try:
            importlib.import_module(name)
        except Exception as exc:  # one bad/optional module must not abort registration
            logger.warning("registry walk: skipping %s (%s)", name, exc)
