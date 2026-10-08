import svx
from tests.integration.sv_root_target_derived import D, derived
from tests.integration.sv_root_target_test import constructed
from svx_mirror.sv_root_e_pkg import E

value = None
final = None


@svx.export(name='inherited_virtual_slot.create')
def create():
    global value
    value = D()
    assert value.check() == 1035
    assert constructed.count(value) == 1 and derived.count(value) == 1
    svx.publish_object('inherited_virtual_slot.d', value)
    svx.display('INHERITED_VIRTUAL_SLOT_CREATED')


@svx.export(name='inherited_virtual_slot.close')
def close():
    assert value.check() == 1042
    svx.close_instance(value)
    assert value.own.value == 1000
    svx.display('INHERITED_VIRTUAL_SLOT_CLOSED')


@svx.export(name='inherited_virtual_slot.create_e')
def create_e():
    global final
    final = E()
    assert final.check() == 1535
    assert constructed.count(final) == 1 and derived.count(final) == 1
    svx.publish_object('inherited_virtual_slot.e', final)


@svx.export(name='inherited_virtual_slot.close_e')
def close_e():
    assert final.check() == 1542
    svx.close_instance(final)
    svx.display('INHERITED_VIRTUAL_SLOT_PYTHON_E_PASS')


@svx.export(name='inherited_virtual_slot.close_sv_e')
def close_sv_e():
    live = [owner for owner in derived if owner is not value and owner is not final]
    assert len(live) == 1 and live[0].check() == 1535
    assert constructed.count(live[0]) == 1
    svx.close_instance(live[0])
    svx.display('INHERITED_VIRTUAL_SLOT_SV_E_PASS')
