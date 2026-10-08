import svx
from svtypes import ExternalStorageError
from svx import _native
from tests.integration.same_module_source import B, D, constructed_b, constructed_d
from svx_mirror.same_package_pkg import C, E
from svx_py.tests.integration.same_module_source import B as BCompanion, D as DCompanion

python_values = []


def verify(value, final):
    assert constructed_b.count(value) == constructed_d.count(value) == 1
    assert _native.inheritance_get(value._svx_remote_object_id) is value
    assert value.check() == (1535 if final else 1035)
    assert value.count.value == 12 and value.retry.value == 23
    assert value.extra.value == 100 and value.own.value == 900 and value.local.value == 7
    if final:
        assert value.observed_python() == 900 and value.e_value.value == 500


def close(value, final):
    fields = (value.count, value.retry, value.extra) + ((value.own, value.e_value) if final else ())
    svx.close_instance(value)
    for field in fields:
        try:
            _ = field.value
        except ExternalStorageError:
            pass
        else:
            raise AssertionError('shared module retained projected storage')
    assert value.local.value == 7
    if not final:
        assert value.own.value == 900


@svx.export(name='same_module.types')
def types():
    assert D.__bases__ == (C, B)
    assert issubclass(C, BCompanion) and issubclass(E, DCompanion)
    for cls in (C, E, BCompanion, DCompanion):
        assert cls.__qualname__ == cls.__name__
    from svx_mirror.same_package_pkg import C as again_c
    from svx_py.tests.integration.same_module_source import B as again_b
    assert again_c is C and again_b is BCompanion
    svx.display('SAME_MODULE_TYPES_PASS')


@svx.export(name='same_module.create')
def create():
    for name, cls, final in (('d', D, False), ('e', E, True)):
        value = cls()
        verify(value, final)
        python_values.append((value, final))
        svx.publish_object('same_module.' + name, value)
    assert python_values[0][0]._svx_remote_object_id != python_values[1][0]._svx_remote_object_id
    svx.display('SAME_MODULE_PYTHON_PASS')


@svx.export(name='same_module.close')
def close_python():
    for value, final in python_values:
        verify(value, final)
        close(value, final)
    svx.display('SAME_MODULE_CLOSE_PASS')


@svx.export(name='same_module.verify_sv')
def verify_sv():
    values = [value for value in constructed_d if _native.inheritance_get(value._svx_remote_object_id) is value]
    assert len(values) == 1
    verify(values[0], True)
    close(values[0], True)
    svx.display('SAME_MODULE_SV_PASS')


@svx.export(name='same_module.verify_all_closed')
def verify_all_closed():
    import svx.inheritance as inheritance

    values = {id(value): value for value in (*constructed_b, *constructed_d)}
    assert values
    for value in values.values():
        assert _native.inheritance_get(value._svx_remote_object_id) is None, 'nested receiver still has native binding'
        try:
            _ = value.count.value
        except ExternalStorageError:
            pass
        else:
            raise AssertionError('nested receiver still has live projected storage')
    assert not inheritance._reserved_python_receivers
    svx.display('SAME_MODULE_ALL_CLOSED_PASS')
