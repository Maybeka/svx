import sys
from types import ModuleType

import pytest
from svtypes import Array, Bit, Enum, Int, Logic, Real, ShortReal, Signed, String, SvStruct

from svx.declarations import inheritance_class, manifest_from_declarations
from svx.inheritance import _sv_field_declaration


class DeclaredDefaultMode(Enum[Bit[8]]):
    IDLE = 0
    ACTIVE = 7


class DeclaredDefaultRecord(SvStruct):
    tag = Bit[8](7)
    flags = Logic[4]()


@pytest.mark.parametrize('descriptor, literal', [
    (String('quoted "value"\\path\n'), r'"quoted \"value\"\\path\n"'),
    (Real(2.5), '2.5'),
    (ShortReal(-1.25), '-1.25'),
    (DeclaredDefaultMode(DeclaredDefaultMode.ACTIVE), 'ACTIVE'),
    (DeclaredDefaultRecord(), "'{tag: 8'h7, flags: 'x}"),
    (Array[DeclaredDefaultRecord, 2](), "'{default: '{tag: 8'h7, flags: 'x}}"),
    (Array[DeclaredDefaultRecord, (2, 3)](), "'{default: '{default: '{tag: 8'h7, flags: 'x}}}"),
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
