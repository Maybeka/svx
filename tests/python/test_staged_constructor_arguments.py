import pytest
from svtypes import CodecSession, Int, String

from svx import _native, inheritance, runtime
from svx.declarations import _svtypes_binding
from svx.errors import SVXInheritanceError


CLASS_ID = 'sv://staged_constructor/Child'


@pytest.fixture
def receiver(monkeypatch):
    monkeypatch.setattr(runtime, '_state', runtime.RuntimeState.READY)
    monkeypatch.setattr(runtime, '_codec_session', CodecSession())
    monkeypatch.setattr(inheritance, '_constructor_contracts', {})
    monkeypatch.setattr(inheritance, '_python_subclasses', {})
    inheritance.register_constructor(CLASS_ID, tuple(
        (name, _svtypes_binding(annotation, where=name))
        for name, annotation in (('seed', Int), ('label', String))))

    class Receiver:
        pass

    value = Receiver()
    inheritance.register_python_subclass(CLASS_ID, Receiver)
    monkeypatch.setattr(_native, 'inheritance_get', lambda object_id: value if object_id == 71 else None)
    return value


def record(value):
    payload = inheritance.encode_constructor(CLASS_ID, {'seed': 19, 'label': 'source arguments'})
    inheritance.create_python_instance(inheritance._SV_CONSTRUCTOR_ARGUMENTS_PREFIX + CLASS_ID, 71, payload)
    value._svx_python_portion_initializing = True


def test_staged_super_matches_values_independent_of_record_object_identity(receiver):
    record(receiver)
    inheritance._validate_staged_base_constructor(receiver, CLASS_ID, {'seed': 19, 'label': 'source arguments'})


@pytest.mark.parametrize('values', [
    {'seed': 20, 'label': 'source arguments'},
    {'seed': 19, 'label': 'different'},
])
def test_staged_super_rejects_arguments_not_used_by_actual_sv_constructor(receiver, values):
    record(receiver)
    with pytest.raises(SVXInheritanceError, match='differ from completed SV base'):
        inheritance._validate_staged_base_constructor(receiver, CLASS_ID, values)


def test_staged_super_rejects_missing_actual_stage(receiver):
    receiver._svx_python_portion_initializing = True
    with pytest.raises(SVXInheritanceError, match='no completed SV constructor'):
        inheritance._validate_staged_base_constructor(receiver, CLASS_ID, {'seed': 19, 'label': 'source arguments'})


def test_ordinary_bound_reinitialization_is_not_a_staged_super(receiver):
    inheritance._validate_staged_base_constructor(receiver, CLASS_ID, {'seed': 29, 'label': 'ordinary'})


def test_staged_constructor_cannot_be_recorded_twice(receiver):
    record(receiver)
    with pytest.raises(SVXInheritanceError, match='repeated staged SV constructor'):
        record(receiver)


def test_staged_constructor_requires_the_matching_receiver(receiver):
    with pytest.raises(SVXInheritanceError, match='no staged receiver'):
        inheritance._record_staged_sv_constructor(CLASS_ID, 72, b'')


def test_generated_validation_import_does_not_shadow_constructor_parameter():
    import ast
    from tests.integration.python_unit_schema import manifest_data

    data = manifest_data()
    parameter = '_validate_staged_base_constructor'
    data['classes'][0]['constructor']['parameters'][0]['name'] = parameter
    outputs = inheritance._emit_python_root_artifacts(inheritance.parse_manifest(data))
    module = next(text for path, text in outputs.items() if str(path) == 'svx_mirror/python_unit_pkg.py')
    target = next(node for node in ast.walk(ast.parse(module))
                  if isinstance(node, ast.ClassDef) and node.name == 'Grandchild')
    initializer = next(node for node in target.body if isinstance(node, ast.FunctionDef) and node.name == '__init__')
    assert initializer.args.args[1].arg == parameter
    imports = [alias for node in ast.walk(initializer) if isinstance(node, ast.ImportFrom)
               for alias in node.names if alias.name == parameter]
    assert len(imports) == 1 and imports[0].asname != parameter
    compile(module, 'generated_constructor.py', 'exec')


@pytest.mark.parametrize('change_arguments', [False, True])
def test_generated_bound_initializer_validates_stage_without_second_allocation(receiver, monkeypatch, change_arguments):
    import ast
    from tests.integration.python_unit_schema import manifest_data

    manifest = inheritance.parse_manifest(manifest_data())
    target = manifest.classes[0]
    parameters = target.constructor.parameters
    values = {parameter.name: 19 for parameter in parameters}
    inheritance.register_constructor(
        target.canonical_id,
        tuple((parameter.name, parameter.type_binding.runtime_spec()) for parameter in parameters),
    )
    inheritance.register_python_subclass(target.canonical_id, type(receiver))
    payload = inheritance.encode_constructor(target.canonical_id, values)
    inheritance._record_staged_sv_constructor(target.canonical_id, 71, payload)
    receiver._svx_remote_object_id = 71
    receiver._svx_python_portion_initializing = True
    before = dict(receiver._svx_completed_sv_constructor_arguments)
    monkeypatch.setattr(_native, 'inheritance_create_sv',
                        lambda *args: pytest.fail('allocated a second SV object'))
    outputs = inheritance._emit_python_root_artifacts(manifest)
    module = next(text for path, text in outputs.items()
                  if str(path) == 'svx_mirror/python_unit_pkg.py')
    generated_class = next(node for node in ast.walk(ast.parse(module))
                           if isinstance(node, ast.ClassDef) and node.name == target.name)
    initializer = next(node for node in generated_class.body
                       if isinstance(node, ast.FunctionDef) and node.name == '__init__')
    namespace = {}
    exec(compile(ast.Module(body=[initializer], type_ignores=[]),
                 '<actual generated bound initializer>', 'exec'), namespace)
    if change_arguments:
        values[parameters[0].name] += 1
        with pytest.raises(SVXInheritanceError, match='independent ancestor constructor routing is not yet implemented'):
            namespace['__init__'](receiver, **values)
    else:
        namespace['__init__'](receiver, **values)
    assert receiver._svx_remote_object_id == 71
    assert receiver._svx_completed_sv_constructor_arguments == before
