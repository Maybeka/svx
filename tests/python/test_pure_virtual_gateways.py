import pytest

from svx.inheritance import _emit_sv_dispatch_case, emit_sv_mirrors, parse_manifest
from tests.integration.pure_virtual_schema import manifest_data


@pytest.mark.parametrize('index', [0, 1])
def test_pure_virtual_base_gateway_rejects_without_invoking_a_missing_body(index):
    method = parse_manifest(manifest_data()).classes[0].methods[index]
    text = '\n'.join(_emit_sv_dispatch_case(method, 'super.'))
    assert method.canonical_id in text
    assert 'SVX1|pure_virtual_base|%0d|%s|' in text
    assert 'this.__svx_remote_object_id, method_id' in text
    assert 'ok = 0;' in text and 'response = null;' in text
    assert 'super.' not in text
    assert '.unpack(' not in text and '.pack(' not in text


def test_pure_virtual_callback_override_remains_concrete_and_dynamic_calls_remain_valid():
    manifest = parse_manifest(manifest_data())
    text = emit_sv_mirrors(manifest)
    assert 'virtual function int check(' in text
    assert 'virtual task update(' in text
    assert 'super.check(' not in text and 'super.update(' not in text
    assert 'svx_inheritance_call_python_function' in text
    for method in manifest.classes[0].methods:
        dynamic = '\n'.join(_emit_sv_dispatch_case(method, 'this.target.'))
        assert 'pure_virtual_base' not in dynamic
        assert 'this.target.' + method.name + '(' in dynamic
