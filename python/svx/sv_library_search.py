"""Scoped, demand-driven source-library lookup for the shared SV frontend."""

from contextlib import contextmanager
from contextvars import ContextVar
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from .errors import SVXInheritanceError


_search = ContextVar('svx_sv_library_search', default=None)


@dataclass
class _SearchContext:
    directories: tuple
    extensions: tuple
    top_modules: tuple = ()
    owners: list = field(default_factory=list)


@contextmanager
def library_search(configuration):
    token = _search.set(_SearchContext(tuple(configuration.library_dirs),
                                      tuple(configuration.library_extensions),
                                      tuple(configuration.top_modules)))
    try:
        yield
    finally:
        _search.reset(token)


def _symbols(trees):
    from pyslang.syntax import SyntaxKind
    from .sv_frontend import source_elaboration_mode
    from .sv_scan import _token_text
    known, referenced, reference_set = set(), [], set()
    packages_only = source_elaboration_mode() == 'packages'

    def declare(node):
        header = getattr(node, 'header', node)
        name = _token_text(getattr(header, 'name', ''))
        if name:
            known.add(name)

    def reference(name):
        name = _token_text(name)
        if name and name not in reference_set:
            reference_set.add(name)
            referenced.append(name)

    def scope(node):
        if node.left.kind == SyntaxKind.IdentifierName:
            reference(node.left.identifier)

    visitors = {kind: declare for kind in (
        SyntaxKind.ModuleDeclaration, SyntaxKind.InterfaceDeclaration,
        SyntaxKind.ProgramDeclaration, SyntaxKind.PackageDeclaration, SyntaxKind.UdpDeclaration)}
    visitors.update({SyntaxKind.HierarchyInstantiation: lambda n: None if packages_only else reference(n.type),
                     SyntaxKind.VirtualInterfaceType: lambda n: reference(n.name),
                     SyntaxKind.PackageImportItem: lambda n: reference(n.package),
                     SyntaxKind.ScopedName: scope})
    for _, tree in trees:
        tree.root.visit(lookup_table=visitors)
    return known, referenced


def load_libraries(trees, paths, source_manager, parse_options, compilation_unit):
    """Lookup exact names, directories first and explicit extensions second.

    SourceLoader's built-in search unconditionally adds default suffixes. We
    select candidates ourselves so +libext order is not changed, and use its
    parser for library-unit and inherited-macro handling. No directory globbing.
    """
    search = _search.get()
    if not search or not search.directories:
        return trees
    directories, extensions = search.directories, search.extensions
    extensions = extensions or ('',)
    from pyslang.driver import Driver, SourceLoader
    from .sv_scan import _check_source_diagnostics
    from .source_selection import record_library_query, record_source_trees

    selected, attempted = set(), set()
    explicit = {Path(path).resolve() for path in paths}
    trees = list(trees)
    known, references = _symbols(trees)
    referenced = set(references)
    pending = deque(references)
    while pending:
        requested = pending.popleft()
        if requested in known or requested in attempted:
            continue
        attempted.add(requested)
        # Design-unit identifiers cannot be interpreted as paths or globs.
        if not requested.isascii() or not requested.isidentifier():
            continue
        candidate = resolve_library_file(requested, directories, extensions)
        record_library_query(requested, candidate)
        if candidate is None:
            continue
        if candidate in explicit or candidate in selected:
            raise SVXInheritanceError(f'library file {candidate} does not declare requested unit {requested}')
        selected.add(candidate)
        # Each library is an independent unit. In shared mode Slang gives every
        # library the root unit's macros, not the preceding library's macros.
        # Rebuild that macro environment without reparsing previous libraries.
        loader = SourceLoader(source_manager)
        if compilation_unit:
            for path in paths:
                loader.addFiles(str(path))
        loader.addLibraryFiles('', str(candidate))
        driver = Driver()
        driver.addStandardArgs()
        flags = 'slang --single-unit --libraries-inherit-macros' if compilation_unit else 'slang'
        if not driver.parseCommandLine(flags):
            raise SVXInheritanceError('cannot configure source-library parsing')
        options = driver.createOptionBag()
        if parse_options is not None:
            for name in ('preprocessorOptions', 'lexerOptions', 'parserOptions'):
                value = getattr(parse_options, name)
                if value is not None:
                    setattr(options, name, value)
        loaded = loader.loadAndParseSources(options)
        # Library trees borrow native library and inherited-macro storage.
        search.owners.append((source_manager, loader, driver, options, loaded))
        if loader.errors:
            raise SVXInheritanceError('cannot load selected source library: ' + '; '.join(loader.errors))
        additions = []
        for tree in loaded:
            _check_source_diagnostics(tree, candidate)
            if tree.isLibraryUnit:
                additions.append((candidate, tree))
        found, references = _symbols(additions)
        if requested not in found:
            raise SVXInheritanceError(f'library file {candidate} does not declare requested unit {requested}')
        trees.extend(additions)
        record_source_trees(additions)
        known.update(found)
        for name in references:
            if name not in referenced:
                referenced.add(name)
                pending.append(name)
    return trees


def resolve_library_file(name, directories, extensions):
    """One lookup rule shared by parsing and incremental selection checks."""
    directories = tuple(directories)
    extensions = tuple(extensions) or ('',)
    for directory in directories:
        for extension in extensions:
            filename = (directory / (name + extension)).resolve()
            if filename.is_file():
                return filename
    return None
