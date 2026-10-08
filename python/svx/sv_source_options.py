"""Shared initial preprocessing configuration for SV source parsing."""

from collections.abc import Mapping
import os
from pathlib import Path

from .errors import SVXInheritanceError


def _source_parse_options(predefines, undefines, include_dirs=(), *, discover_proxies=False):
    try:
        from pyslang import Bag
        from pyslang.parsing import PreprocessorOptions
    except ImportError as error:
        raise SVXInheritanceError(
            "SV source scanning requires the optional 'pyslang' dependency; "
            "install SVX with the 'manifest' extra"
        ) from error

    def valid_name(name):
        return isinstance(name, str) and name.isascii() and name.isidentifier()

    if predefines is not None and not isinstance(predefines, Mapping):
        raise TypeError('source predefines must be a name-to-text mapping')
    if isinstance(undefines, str):
        raise TypeError('source undefines must be a sequence of names, not text')
    if isinstance(include_dirs, (str, bytes, os.PathLike)):
        raise TypeError('source include directories must be a sequence of paths')
    directories = []
    for path in include_dirs:
        try:
            directory = os.fspath(path)
        except TypeError as error:
            raise SVXInheritanceError('source include directories require text paths') from error
        if not isinstance(directory, str) or not directory or any(char in directory for char in '\r\n\0'):
            raise SVXInheritanceError('source include directories require nonempty single-line text paths')
        directories.append(directory)
    options = PreprocessorOptions()
    definitions = []
    for name, value in (predefines or {}).items():
        if not valid_name(name) or (value is not None and (not isinstance(value, str)
                or any(char in value for char in '\r\n\0'))):
            raise SVXInheritanceError('source predefines require identifier names and single-line text values')
        definitions.append(name if value is None else name + '=' + value)
    names = tuple(undefines)
    if not all(valid_name(name) for name in names):
        raise SVXInheritanceError('source undefines require identifier names')
    options.predefines = definitions
    if discover_proxies:
        if "SVX_PY_PROXY" in (predefines or {}) or "SVX_PY_PROXY" in names:
            raise SVXInheritanceError("SVX_PY_PROXY is reserved during source discovery")
        options.predefines = [*definitions,
            "SVX_PY_PROXY(N,I,B)=(* __svx_discovery_python_class_id = I *) class N extends B; endclass"]
    options.undefines = list(names)
    options.additionalIncludePaths = directories
    return Bag([options])


def _source_dependencies(paths, *, predefines=None, undefines=(), include_dirs=(),
                         compilation_unit=False):
    from .sv_scan import _parse_sources, _pyslang

    sources = [Path(path).resolve() for path in paths]
    dependencies = set(sources)
    if not sources:
        return dependencies
    options = _source_parse_options(predefines, undefines, include_dirs, discover_proxies=True)
    for _, tree in _parse_sources(_pyslang(), sources, parse_options=options,
                                  compilation_unit=compilation_unit):
        manager = tree.sourceManager
        for buffer in manager.getAllBuffers():
            name = manager.getRawFileName(buffer)
            # Macro expansion buffers are synthetic, not filesystem inputs.
            if name and not name.startswith('<'):
                dependencies.add(Path(name).resolve())
    return dependencies
