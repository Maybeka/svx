import svx
from svtypes import ExternalStorageError
from svx import _native
from svx_mirror.python_root_e_probe_pkg import Grandchild
from tests.integration.python_root_proxy_test import constructed_roots


_python_e = None


def verify(value, seed):
    assert value._svx_initialized_python_portions == {
        'py://tests/integration/python_root/Root', 'py://tests/integration/python_root/Derived',
    }
    assert constructed_roots.count(value) == 1
    assert value.observed_value() == seed
    assert value.observed_python() == 1000
    assert value.check(1) == seed + 1601
    assert value.fixed(1) == seed + 701
    assert value.count.value == seed and value.own_value.value == 1000
    assert value.e_value.value == 500


def close(value):
    fields = (value.count, value.child_value, value.own_value, value.e_value)
    svx.close_instance(value)
    for field in fields:
        try:
            _ = field.value
        except ExternalStorageError:
            pass
        else:
            raise AssertionError('qualified E close retained live storage')
    assert value.local.value == 7


@svx.export(name='python_root_namespaces.create_e')
def create_e():
    global _python_e
    _python_e = Grandchild(91)
    verify(_python_e, 91)
    svx.publish_object('python_root_namespaces.e', _python_e)
    svx.display('PYTHON_ROOT_NAMESPACE_PYTHON_E_CREATED')


@svx.export(name='python_root_namespaces.close_e')
def close_e():
    assert _python_e.count.value == 94
    assert _python_e.check(1) == 1695
    close(_python_e)
    svx.display('PYTHON_ROOT_NAMESPACE_PYTHON_E_PASS')


@svx.export(name='python_root_namespaces.verify_sv_e')
def verify_sv_e():
    candidates = [value for value in constructed_roots
                  if getattr(value, '__svx_foreign_class_id__', None) == 'sv://python_root_e_probe_pkg/Grandchild'
                  and _native.inheritance_get(value._svx_remote_object_id) is value]
    assert len(candidates) == 1
    value = candidates[0]
    verify(value, 93)
    value.own_value.value = 2000
    assert value.check(1) == 2694
    close(value)
    svx.display('PYTHON_ROOT_NAMESPACE_SV_E_PASS')
