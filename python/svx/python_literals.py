"""Readable generated literal data, without key-width-dependent indentation."""


class LiteralName:
    """A generation-time reference to a previously emitted data constant."""

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


def format_literal(value, *, level=0, width=100):
    indent = '    ' * level
    child_indent = indent + '    '
    if isinstance(value, dict):
        if not value:
            return '{}'
        items = [child_indent + repr(key) + ': ' + format_literal(item, level=level + 1, width=width) + ','
                 for key, item in value.items()]
        return '{\n' + '\n'.join(items) + '\n' + indent + '}'
    if isinstance(value, (tuple, list)):
        if not value:
            return repr(value)
        if all(not isinstance(item, (dict, tuple, list)) for item in value):
            compact = repr(value)
            if len(indent) + len(compact) <= width:
                return compact
        # Keep the name/direction beside its type, not in a vertical stack.
        if (isinstance(value, tuple) and len(value) > 1 and isinstance(value[-1], dict)
                and all(not isinstance(item, (dict, tuple, list)) for item in value[:-1])):
            prefix = '(' + ', '.join(repr(item) for item in value[:-1]) + ', '
            if len(indent) + len(prefix) + 1 <= width:
                return prefix + format_literal(value[-1], level=level, width=width) + ')'
        opening, closing = ('(', ')') if isinstance(value, tuple) else ('[', ']')
        items = [child_indent + format_literal(item, level=level + 1, width=width) + ','
                 for item in value]
        return opening + '\n' + '\n'.join(items) + '\n' + indent + closing
    return repr(value)
