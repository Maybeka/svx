import sys
from types import ModuleType

import pytest
import svtypes
from svtypes import Array, Bit, Enum, Int, Logic, Real, ShortReal, Signed, String, SvPackedStruct

from svx.declarations import inheritance_class, manifest_from_declarations
from svx.inheritance import _sv_field_declaration


class DeclaredDefaultMode(Enum[Bit[8]]):
    IDLE = 0
    ACTIVE = 7


class DeclaredDefaultRecord(SvPackedStruct):
    tag = Bit[8](7)
    flags = Logic[4]()


_SHARED_FIELD_OPS = 'svtypes.generated-field-operations.v1' in svtypes.runtime_capabilities().provided
_RECORD_DEFAULT = ('DeclaredDefaultRecord_packer::svtypes_default()' if _SHARED_FIELD_OPS
                   else "'{tag: 8'h7, flags: 'x}")


@pytest.mark.parametrize('descriptor, literal', [
    (String('quoted "value"\\path\n'), r'"quoted \"value\"\\path\n"'),
    (Real(2.5), '2.5'),
    (ShortReal(-1.25), '-1.25'),
    (DeclaredDefaultMode(DeclaredDefaultMode.ACTIVE), 'ACTIVE'),
    (DeclaredDefaultRecord(), _RECORD_DEFAULT),
    (Array[DeclaredDefaultRecord, 2](), "'{default: " + _RECORD_DEFAULT + '}'),
    (Array[DeclaredDefaultRecord, (2, 3)](), "'{default: '{default: " + _RECORD_DEFAULT + '}}'),
])
def test_other_declared_initializers_survive_the_manifest(descriptor, literal, monkeypatch):
    module = ModuleType('other_default_probe')
    monkeypatch.setitem(sys.modules, module.__name__, module)
    cls = type('Owner', (), {'__module__': module.__name__, 'value': descriptor})
    module.Owner = inheritance_class(canonical_id='py://other_default_probe/Owner')(cls)
    field = manifest_from_declarations(python_modules=[module]).classes[0].fields[0]
    assert _sv_field_declaration(field).endswith(' = ' + literal)


@pytest.mark.parametrize('descriptor', [Int(17), Int(-3), Bit[9](257), Bit[8, Signed](-4)])
def test_packed_field_defaults_are_rendered_by_public_svtypes(descriptor, monkeypatch):
    module = ModuleType('packed_default_probe')
    monkeypatch.setitem(sys.modules, module.__name__, module)
    cls = type('Owner', (), {'__module__': module.__name__, 'count': descriptor})
    module.Owner = inheritance_class(canonical_id='py://packed_default_probe/Owner')(cls)
    field = manifest_from_declarations(python_modules=[module]).classes[0].fields[0]
    assert _sv_field_declaration(field).endswith(' = ' + descriptor.sv_repr())


def test_four_state_declared_initial_value_is_not_lost(monkeypatch):
    module = ModuleType('logic_default_probe')
    monkeypatch.setitem(sys.modules, module.__name__, module)
    cls = type('Owner', (), {'__module__': module.__name__, 'count': Logic[4]('xz10')})
    module.Owner = inheritance_class(canonical_id='py://logic_default_probe/Owner')(cls)
    field = manifest_from_declarations(python_modules=[module]).classes[0].fields[0]
    assert _sv_field_declaration(field).endswith(" = 4'bxz10")
