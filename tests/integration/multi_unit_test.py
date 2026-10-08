import svx
from svtypes import ExternalStorageError
from svx import _native
from tests.integration.multi_unit_source import B, D, constructed_b, constructed_d
from svx_mirror.multi_c_pkg import C
from svx_mirror.multi_e_pkg import E
from svx_py.tests.integration.multi_unit_source import B as BC, D as DC

python_values = []


def verify(value, final):
    assert constructed_b.count(value) == constructed_d.count(value) == 1
    assert _native.inheritance_get(value._svx_remote_object_id) is value
    assert value.check() == (1535 if final else 1035)
    assert (value.count.value, value.retry.value, value.extra.value, value.own.value, value.local.value) == (12, 23, 100, 900, 7)
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
            raise AssertionError('multi-input projected storage remained live')
    assert value.local.value == 7
    if not final:
        assert value.own.value == 900


@svx.export(name='multi_unit.types')
def types():
    assert D.__bases__ == (C, B)
    assert issubclass(C, BC) and issubclass(E, DC)
    for cls in (C, E, BC, DC):
        assert cls.__qualname__ == cls.__name__
    svx.display('MULTI_UNIT_TYPES_PASS')


@svx.export(name='multi_unit.create')
def create():
    for name, cls, final in (('d', D, False), ('e', E, True)):
        value = cls()
        verify(value, final)
        python_values.append((value, final))
        svx.publish_object('multi_unit.' + name, value)
    assert python_values[0][0]._svx_remote_object_id != python_values[1][0]._svx_remote_object_id
    svx.display('MULTI_UNIT_PYTHON_PASS')


@svx.export(name='multi_unit.close')
def close_python():
    for value, final in python_values:
        verify(value, final)
        close(value, final)
    svx.display('MULTI_UNIT_CLOSE_PASS')


@svx.export(name='multi_unit.verify_sv')
def verify_sv():
    values = [value for value in constructed_d if _native.inheritance_get(value._svx_remote_object_id) is value]
    assert len(values) == 1
    verify(values[0], True)
    close(values[0], True)
    svx.display('MULTI_UNIT_SV_PASS')
