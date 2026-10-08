import svx
from svtypes import ExternalStorageError
from svx import _native
from tests.integration.python_unit_source import Root, Derived, constructed_roots, constructed_derived
from svx_mirror.python_unit_pkg import Child, Grandchild
from svx_py.tests.integration.python_unit_source import Root as RootCompanion, Derived as DerivedCompanion

python_values = []


@svx.export(name='python_unit.mismatch')
def mismatch():
    from tests.integration import python_unit_source
    python_unit_source.mismatch_super = True


def verify(value, seed, final):
    assert constructed_roots.count(value) == constructed_derived.count(value) == 1
    assert _native.inheritance_get(value._svx_remote_object_id) is value
    assert value.count.value == value.observed_value() == seed
    assert value.check(1) == seed + (1601 if final else 1101)
    assert value.own_value.value == 1000 and value.local.value == 7
    if final:
        assert value.observed_python() == 1000 and value.e_value.value == 500


def close(value, final):
    fields = (value.count, value.child_value) + ((value.own_value, value.e_value) if final else ())
    svx.close_instance(value)
    for field in fields:
        try:
            _ = field.value
        except ExternalStorageError:
            pass
        else:
            raise AssertionError('Python-root source unit kept projected storage alive')
    assert value.local.value == 7
    if not final:
        assert value.own_value.value == 1000


@svx.export(name='python_unit.types')
def types():
    from svtypes import Int
    from svx.inheritance import invoke_sv_static

    assert Derived.__bases__ == (Child, Root)
    assert issubclass(Child, RootCompanion) and issubclass(Grandchild, DerivedCompanion)
    for cls in (Child, Grandchild, RootCompanion, DerivedCompanion):
        assert cls.__qualname__ == cls.__name__
    assert Root.scale(7) == Child.scale(7) == 21
    root_id = 'py://tests/integration/python_unit/Root'
    assert invoke_sv_static(root_id, root_id + '#scale', {'delta': Int(7)}) == 21
    invoke_sv_static(root_id, root_id + '#wait_once', {})
    svx.display('PYTHON_UNIT_STATIC_BRIDGE_PASS')
    svx.display('PYTHON_UNIT_TYPES_PASS')


@svx.export(name='python_unit.create')
def create():
    for name, cls, seed, final in (('derived', Derived, 23, False), ('final', Grandchild, 31, True)):
        value = cls(seed)
        verify(value, seed, final)
        python_values.append((value, seed, final))
        svx.publish_object('python_unit.' + name, value)
    assert python_values[0][0]._svx_remote_object_id != python_values[1][0]._svx_remote_object_id
    svx.display('PYTHON_UNIT_PYTHON_PASS')


@svx.export(name='python_unit.close')
def close_python():
    for value, seed, final in python_values:
        verify(value, seed, final)
        close(value, final)
    svx.display('PYTHON_UNIT_CLOSE_PASS')


@svx.export(name='python_unit.verify_sv')
def verify_sv():
    values = [value for value in constructed_derived if _native.inheritance_get(value._svx_remote_object_id) is value]
    assert len(values) == 1
    verify(values[0], 19, True)
    close(values[0], True)
    svx.display('PYTHON_UNIT_SV_PASS')
