import inspect
from pathlib import PurePosixPath

import pytest

from svx import _native
from svx.inheritance import emit_python_mirrors, emit_sv_mirrors, parse_manifest
from tests.integration.sv_field_mirror_schema import manifest_data


def boundary_manifest(*, fields=True):
    data = manifest_data()
    data['classes'][0]['constructor']['initiator'] = 'sv'
    if not fields:
        data['classes'][0]['fields'] = []
    return parse_manifest(data)


def test_python_proxy_initializes_after_its_sv_field_initializers():
    from tests.integration.field_projection_schema import manifest_data as projection_data

    text = emit_sv_mirrors(parse_manifest(projection_data()))
    root = text.split('class Base extends field_pkg::Base', 1)[1].split('endclass', 1)[0]
    proxy = text.split('class PythonLayer extends Base', 1)[1].split('endclass', 1)[0]
    assert 'if (!this.__svx_defer_python_constructor()) begin' in root
    assert root.index('register_object(') < root.index('if (!this.__svx_defer_python_constructor())')
    assert proxy.index('super.new(') < proxy.index('svx_inheritance_create_python_function(')
    assert '"sv://field_pkg/Base"' in proxy
    assert 'if (svx_object_id_1 == 0) begin' in proxy


@pytest.mark.parametrize('fields', [False, True])
@pytest.mark.parametrize('standalone', [False, True])
def test_sv_origin_declaration_also_supports_python_construction(monkeypatch, fields, standalone):
    calls = []
    monkeypatch.setattr(_native, 'inheritance_create_sv',
                        lambda class_id, payload: calls.append((class_id, payload)) or 71)
    monkeypatch.setattr(_native, 'inheritance_bind', lambda *args: None)
    manifest = boundary_manifest(fields=fields)
    if standalone:
        from dataclasses import replace
        manifest = replace(manifest, classes=manifest.classes[:1])
    text = emit_python_mirrors(manifest)[PurePosixPath('svx_mirror/field_owner_pkg.py')]
    namespace = {'__name__': 'tests.generated_sv_initiated_boundary'}
    exec(compile(text, '<SV-initiated boundary>', 'exec'), namespace)
    Base = namespace['Base']
    projected = []
    monkeypatch.setattr(Base, '_svx_bind_projected_fields',
                        lambda instance, fields: projected.append(fields))
    value = Base()
    assert value._svx_remote_object_id == 71
    assert calls == [('sv://field_owner_pkg/Base', b'')]
    assert projected == ([{'count': 'sv://field_owner_pkg/Base.count'}] if fields else [{}])


def test_sv_initiated_boundary_initializer_accepts_already_bound_receiver(monkeypatch):
    monkeypatch.setattr(_native, 'inheritance_create_sv',
                        lambda *args: pytest.fail('reallocated an SV-origin receiver'))
    text = emit_python_mirrors(boundary_manifest())[PurePosixPath('svx_mirror/field_owner_pkg.py')]
    namespace = {'__name__': 'tests.generated_sv_initiated_bound_receiver'}
    exec(compile(text, '<SV-initiated boundary>', 'exec'), namespace)
    Base = namespace['Base']
    value = Base.__new__(Base)
    value._svx_bind_remote_object(71)
    Base.__init__(value)
    assert value._svx_remote_object_id == 71


@pytest.mark.parametrize('standalone', [False, True])
def test_sv_initiated_boundary_preserves_parameter_names_and_order(monkeypatch, standalone):
    from svx import inheritance
    from svx import runtime
    import svtypes
    data = manifest_data()
    base = data['classes'][0]
    monkeypatch.setattr(inheritance, '_constructor_contracts', {})
    session = svtypes.CodecSession(origin=31)
    monkeypatch.setattr(runtime, '_state', runtime.RuntimeState.READY)
    monkeypatch.setattr(runtime, '_codec_session', session)
    base['constructor'] = {'initiator': 'sv', 'parameters': [
        {'name': name, 'type': base['fields'][0]['type']} for name in ('self', 'object_id')
    ]}
    data['classes'][1]['base_lineage'][0] = base
    if standalone:
        base['fields'] = []
        data['classes'] = data['classes'][:1]
    monkeypatch.setattr(_native, 'inheritance_create_sv', lambda *args: 72)
    monkeypatch.setattr(_native, 'inheritance_bind', lambda *args: None)
    text = emit_python_mirrors(parse_manifest(data))[PurePosixPath('svx_mirror/field_owner_pkg.py')]
    namespace = {'__name__': 'tests.generated_sv_initiated_signature'}
    exec(compile(text, '<SV-initiated signature>', 'exec'), namespace)
    Base = namespace['Base']
    assert tuple(inspect.signature(Base).parameters) == ('self', 'object_id')
    monkeypatch.setattr(Base, '_svx_bind_projected_fields', lambda *args: None)
    assert Base(11, 12)._svx_remote_object_id == 72
    value = Base.__new__(Base)
    value._svx_bind_remote_object(71)
    Base.__init__(value, 11, 12)
    assert value._svx_remote_object_id == 71
    session.close()
