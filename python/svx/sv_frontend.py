"""Phase-local semantic analysis over command-owned, verified source syntax.

The dependency observer can supply immutable raw trees after fresh content and
lookup validation. Semantic graphs remain local to each analysis scope; no AST
or source manager is retained by the observation context after the command.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field


_analysis = ContextVar('svx_source_analysis', default=None)
_elaboration = ContextVar('svx_source_elaboration', default='all')


def source_elaboration_mode():
    return _elaboration.get()


@contextmanager
def source_elaboration(mode='all'):
    if mode not in {'all', 'packages'}:
        raise ValueError(f'unsupported SV elaboration mode: {mode!r}')
    token = _elaboration.set(mode)
    try:
        yield
    finally:
        _elaboration.reset(token)


def elaborate_sources(compilation):
    """Elaborate original package semantics without implicit DUT tops on request.

    Keep every original syntax tree and its preprocessing context. The empty top
    affects semantic elaboration only; it is never emitted or compiled into SV.
    """
    from .sv_library_search import _search
    library = _search.get()
    tops = library.top_modules if library is not None else ()
    if _elaboration.get() == 'packages' or tops:
        from pyslang import Bag
        from pyslang.ast import Compilation, CompilationOptions
        from pyslang.syntax import SyntaxTree

        top = None
        if _elaboration.get() == 'packages':
            occupied = {definition.name for definition in compilation.getDefinitions()}
            top = 'svx_export_analysis_root'
            while top in occupied:
                top += '_'
        options = CompilationOptions()
        options.topModules = {top} if top is not None else set(tops)
        selected = Compilation(Bag([options]))
        for tree in compilation.getSyntaxTrees():
            selected.addSyntaxTree(tree)
        if top is not None:
            selected.addSyntaxTree(SyntaxTree.fromText(
                f'module {top}; endmodule', compilation.sourceManager))
        compilation = selected
    compilation.getRoot()
    return compilation


def compile_source_trees(trees):
    """Share default semantic compilations of identical command-owned trees.

    Probe consumers must create their own compilation before adding any trees;
    a returned compilation is read-only. Tree identity includes preprocessing
    and source grouping, while the key also preserves elaboration/library policy.
    """
    from time import perf_counter
    from pyslang.ast import Compilation
    from .sv_library_search import _search

    trees = tuple(trees)
    state = _analysis.get()
    library = _search.get()
    shared = (state is not None and trees
              and all(tree.sourceManager is state.source_manager for tree in trees))
    key = (tuple(map(id, trees)), source_elaboration_mode(), id(library))
    if shared and key in state.compilations:
        state.semantic_reuses += 1
        return state.compilations[key]
    start = perf_counter()
    compilation = Compilation()
    for tree in trees:
        compilation.addSyntaxTree(tree)
    compilation = elaborate_sources(compilation)
    if shared:
        state.compilations[key] = compilation
        state.owners.append((trees, library))
        state.semantic_builds += 1
        state.semantic_seconds += perf_counter() - start
    return compilation


@dataclass
class SourceAnalysis:
    source_manager: object
    trees: dict = field(default_factory=dict)
    owners: list = field(default_factory=list)
    parse_batches: int = 0
    syntax_reuses: int = 0
    parse_seconds: float = 0.0
    compilations: dict = field(default_factory=dict)
    semantic_builds: int = 0
    semantic_reuses: int = 0
    semantic_seconds: float = 0.0
    class_fact_tables: dict = field(default_factory=dict)
    class_fact_builds: int = 0
    class_fact_reuses: int = 0
    package_imports: dict = field(default_factory=dict)


@contextmanager
def source_analysis():
    """Own phase-local consumers, borrowing verified command syntax when safe."""
    from pyslang import SourceManager

    state = SourceAnalysis(SourceManager())
    token = _analysis.set(state)
    try:
        yield state
    finally:
        _analysis.reset(token)


def analysis_source_manager():
    from pyslang import SourceManager

    state = _analysis.get()
    return state.source_manager if state is not None else SourceManager()
