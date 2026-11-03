"""Generation-time member locations; never consulted by ordinary execution."""
import ast
import json
from pathlib import PurePosixPath


def member_locations(identifiers, python_sources, sv_sources, *, python_prefix=''):
    wanted = set(identifiers)
    found = {identifier: [] for identifier in sorted(wanted)}
    for path, source in sorted(python_sources.items(), key=lambda item: str(item[0])):
        if path.suffix != '.py' or 'svx_support' in path.parts:
            continue
        seen = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in wanted:
                key = (node.value, node.lineno)
                if key not in seen:
                    found[node.value].append({'language': 'python',
                        'path': (PurePosixPath(python_prefix)/path).as_posix(), 'line': node.lineno})
                    seen.add(key)
    decoder = json.JSONDecoder()
    for path, source in sorted(sv_sources.items(), key=lambda item: str(item[0])):
        if path.suffix != '.sv':
            continue
        for number, line in enumerate(source.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith('// Core operation: '):
                identifier = stripped.removeprefix('// Core operation: ').strip()
                if identifier in wanted:
                    found[identifier].append({'language': 'systemverilog', 'path': path.as_posix(), 'line': number})
                continue
            if not stripped.startswith('"'):
                continue
            try:
                identifier, end = decoder.raw_decode(stripped)
            except ValueError:
                continue
            if identifier in wanted and stripped[end:].lstrip().startswith(':'):
                found[identifier].append({'language': 'systemverilog', 'path': path.as_posix(), 'line': number})
    return {identifier: locations for identifier, locations in found.items() if locations}
