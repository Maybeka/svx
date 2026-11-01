"""Preserve selected, ordinary SV class inheritance in public Python modules."""

import ast
from pathlib import PurePosixPath


def _inheritance_body(body, node, source, parent):
    inherited_fields = {field.name for portion in (*parent.base_lineage, parent)
                        for field in portion.fields} - {field.name for field in source.fields}
    for member in reversed(node.body):
        if (isinstance(member, ast.Assign) and len(member.targets) == 1
                and isinstance(member.targets[0], ast.Name)
                and member.targets[0].id in inherited_fields):
            del body[member.lineno - node.lineno:member.end_lineno - node.lineno + 1]
    from .inheritance import _python_module_for

    indent = body[0][:len(body[0]) - len(body[0].lstrip())]
    body[0] = indent + f'class {source.name}(_SVXSelectedBase):'
    body.insert(0, indent + f'from {_python_module_for(parent)} import {parent.name} as _SVXSelectedBase')
    return body


def preserve_package_inheritance(manifest, emitted, *, staged=False):
    from .inheritance import (
        _emit_deferred_python_class, _emit_deferred_python_footer,
        _python_module_for, projection_plans,
    )

    # Alternating language chains already have their own construction planner.
    if not staged and any(plan.steps for plan in projection_plans(manifest)):
        return emitted
    selected = {item.canonical_id: item for item in manifest.classes if item.language == 'sv'}
    parents = {}
    for item in selected.values():
        for ancestor in reversed(item.base_lineage):
            if ancestor.language != 'sv':
                break
            if ancestor.canonical_id in selected:
                parents[item.canonical_id] = selected[ancestor.canonical_id]
                break
    if not parents:
        return emitted

    result = dict(emitted)
    affected = set(parents) | {item.canonical_id for item in parents.values()}
    modules = {_python_module_for(selected[key]) for key in affected}
    for module in sorted(modules):
        path = PurePosixPath(*module.split('.')).with_suffix('.py')
        if path not in result:
            path = PurePosixPath(*module.split('.'), '__init__.py')
            if path not in result:
                continue
        text = result[path]
        lines = text.splitlines()
        sources = {item.name: item for item in selected.values()
                   if item.canonical_id in affected and _python_module_for(item) == module}
        replacements = []
        deferred = {}
        deferred_namespaces = set()
        tree = ast.parse(text)
        nodes = tree.body
        public_classes = set()
        for candidate in ast.walk(tree):
            if isinstance(candidate, ast.ClassDef) and any(
                    isinstance(member, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == '__svx_foreign_class_id__'
                            for target in member.targets)
                    and isinstance(member.value, ast.Constant)
                    and isinstance(member.value.value, str) and member.value.value.startswith('sv://')
                    for member in candidate.body):
                public_classes.add(candidate.name)
        for index, node in enumerate(nodes):
            if not isinstance(node, ast.ClassDef) or node.name not in sources:
                continue
            source = sources[node.name]
            parent = parents.get(source.canonical_id)
            end = node.end_lineno
            # Source-mirror registration belongs to the same lazy declaration.
            for following in nodes[index + 1:]:
                if (isinstance(following, ast.Assign) and len(following.targets) == 1
                        and isinstance(following.targets[0], ast.Attribute)
                        and isinstance(following.targets[0].value, ast.Name)
                        and following.targets[0].value.id == node.name
                        and following.targets[0].attr in {'__module__', '__qualname__'}):
                    end = following.end_lineno
                    continue
                if isinstance(following, ast.Try) and len(following.body) == 1:
                    expression = following.body[0]
                    if isinstance(expression, ast.Expr):
                        target = expression.value
                        while isinstance(target, ast.Attribute):
                            target = target.value
                        if isinstance(target, ast.Name) and target.id == node.name:
                            end = following.end_lineno
                            continue
                if isinstance(following, ast.Assign) and len(following.targets) == 1:
                    target = following.targets[0]
                    while isinstance(target, ast.Attribute):
                        target = target.value
                    if isinstance(target, ast.Name) and target.id == node.name:
                        end = following.end_lineno
                        continue
                if not isinstance(following, ast.Expr) or not isinstance(following.value, ast.Call):
                    break
                call = following.value
                if (not isinstance(call.func, ast.Name)
                        or call.func.id not in {'_register_source_mirror_implementation', 'register_python_subclass'}
                        or not call.args or not isinstance(call.args[-1], ast.Name)
                        or call.args[-1].id != node.name):
                    break
                end = following.end_lineno
            body = lines[node.lineno - 1:end]
            if parent is not None:
                body = _inheritance_body(body, node, source, parent)
            # Creating a generated SV descendant is not registering a Python
            # override of its SV ancestor. User-defined children still register.
            for offset, line in enumerate(body):
                if line.lstrip().startswith('register_python_subclass(') and line.startswith('        '):
                    body[offset:offset + 1] = [
                        line[:len(line) - len(line.lstrip())] + "if '__svx_foreign_class_id__' not in cls.__dict__:",
                        '    ' + line,
                    ]
                    break
            # A root with class-owned value declarations already publishes a
            # temporary value namespace during contract imports. Keep its normal
            # class/attachment/registration ordering instead of deferring only
            # the class and leaving registration pointed at that namespace.
            nested_values = any(value.module == module and value.qualname.startswith(source.name + '.')
                                for value in (*manifest.value_types, *manifest.constants))
            if parent is None and nested_values:
                replacements.append((node.lineno - 1, end, body))
                continue
            loader = '_svx_load_selected_' + source.name
            declaration = _emit_deferred_python_class(source, '\n'.join(body), loader, value_namespace=nested_values)
            if any(f'{source.name}.__qualname__ =' in line for line in body):
                declaration[-4] = ''
            replacements.append((node.lineno - 1, end, declaration))
            deferred[source.name] = loader
            if nested_values:
                deferred_namespaces.add(source.name)
        # Source-managed views already live in lazy loader functions. Keep their
        # construction/registration code and adjust only the native SV segment.
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node in nodes or node.name not in sources:
                continue
            source = sources[node.name]
            parent = parents.get(source.canonical_id)
            if parent is None:
                continue
            body = _inheritance_body(lines[node.lineno - 1:node.end_lineno], node, source, parent)
            replacements.append((node.lineno - 1, node.end_lineno, body))
        if not replacements:
            continue
        for start, end, replacement in sorted(replacements, reverse=True):
            lines[start:end] = replacement
        if deferred:
            lines.extend(_emit_deferred_python_footer(deferred, chain=True))
        for name in sorted(deferred_namespaces):
            lines.extend([f'if not isinstance(globals().get({name!r}), type):',
                          f'    globals().pop({name!r}, None)'])
        public_names = repr(tuple(sorted(public_classes)))
        lines.extend([
            f'__all__ = sorted({{name for name in globals() if not name.startswith("_")}} | set({public_names}))',
            '',
            'def __dir__():',
            f'    return sorted(set(globals()) | set({public_names}))',
        ])
        result[path] = '\n'.join(lines).rstrip() + '\n'
    return result
