"""Scoped, demand-driven source-library lookup for the shared SV frontend."""

from contextlib import contextmanager
from contextvars import ContextVar
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

    selected, attempted = [], set()
    owners = (source_manager,)
    explicit = {Path(path).resolve() for path in paths}
    while True:
        known, references = _symbols(trees)
        candidate = None
        requested = None
        for name in references:
            if name in known or name in attempted:
                continue
            attempted.add(name)
            # Design-unit identifiers cannot be interpreted as paths or globs.
            if not name.isascii() or not name.isidentifier():
                continue
            candidate = resolve_library_file(name, directories, extensions)
            record_library_query(name, candidate)
            if candidate:
                requested = name
                break
        if candidate is None:
            # Driver-produced trees borrow parser/macro storage. Keep it alive
            # for all semantic passes in this scoped discovery/generation call.
            search.owners.append(owners)
            return trees
        if candidate in explicit or candidate in selected:
            raise SVXInheritanceError(f'library file {candidate} does not declare requested unit {requested}')
        selected.append(candidate)
        # Load only selected files, with no native -y search or implicit suffixes.
        loader = SourceLoader(source_manager)
        for path in paths:
            loader.addFiles(str(path))
        for path in selected:
            loader.addLibraryFiles('', str(path))
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
        owners = (source_manager, loader, driver, options, loaded)
        if loader.errors:
            raise SVXInheritanceError('cannot load selected source library: ' + '; '.join(loader.errors))
        trees = []
        for tree in loaded:
            _check_source_diagnostics(tree, candidate)
            buffers = tree.sourceManager.getAllBuffers()
            filename = next((tree.sourceManager.getRawFileName(buffer) for buffer in buffers
                             if tree.sourceManager.getRawFileName(buffer)), str(paths[0]))
            trees.append((Path(filename), tree))
        record_source_trees(trees)
        found, _ = _symbols(trees)
        if requested not in found:
            raise SVXInheritanceError(f'library file {candidate} does not declare requested unit {requested}')


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
