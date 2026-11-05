import ast

import pytest

from svx.python_literals import format_literal


@pytest.mark.parametrize('value', [
    {}, (), [], None, True, b'\x00\xff',
    {'a': ({'b': [1, (2,), [], ()]},)},
    (('value', 'input', {'name': 'example'}),),
    {'unicode': '\u4e2d\u6587\f\r\n', 'long': 'x' * 300},
    tuple('value_' + str(index) for index in range(30)),
])
def test_literal_format_preserves_python_data_and_container_types(value):
    text = format_literal(value)
    assert ast.literal_eval(text) == value
    assert type(ast.literal_eval(text)) is type(value)
    assert all((len(line) - len(line.lstrip())) % 4 == 0 for line in text.splitlines())


def test_long_method_ids_do_not_shift_the_contract_body():
    def contract(method):
        return format_literal({method: {'timing': 'task', 'parameters': (
            ('value', 'input', {'svtypes': {'kind': 'packed', 'width': 8}}),
        )}})
    short = contract('A#send')
    long = contract('package/' * 40 + 'Driver#send')
    assert short.splitlines()[2:] == long.splitlines()[2:]
    assert "            ('value', 'input', {" in long
    assert "        'timing': 'task'," in long
    assert ' ' * 24 not in long


def test_binding_key_order_is_retained():
    value = {'timing': 'function', 'parameters': (), 'request': (), 'response': (), 'external_targets': ()}
    result = ast.literal_eval(format_literal(value))
    assert list(result) == list(value)
