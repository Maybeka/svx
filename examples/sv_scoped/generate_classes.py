"""Use native classes from generated lanes without moving their definitions."""
import svx
from svtypes import Int
from svx_mirror_instance.tb_generate_classes.a.svx_scope_4_lane_p0.active.classes import Driver as DriverA0
from svx_mirror_instance.tb_generate_classes.a.svx_scope_4_lane_p1.active.classes import Driver as DriverA1
from svx_mirror_instance.tb_generate_classes.b.svx_scope_4_lane_p0.active.classes import Driver as DriverB0
from svx_mirror_instance.tb_generate_classes.b.svx_scope_4_lane_p1.active.classes import Driver as DriverB1
from svx_mirror_instance.tb_generate_classes.c.svx_scope_4_lane_p0.active.classes import Driver as DriverC0
from svx_mirror_instance.tb_generate_classes.c.svx_scope_4_lane_p1.active.classes import Driver as DriverC1


class PythonDriver(DriverB1):
    def status(self):
        return super().status()+1000


@svx.export(name='generate_classes.run')
def run():
    types=(DriverA0,DriverA1,DriverB0,PythonDriver,DriverC0,DriverC1)
    values=[cls(Int(index+1)) for index,cls in enumerate(types)]
    assert [value.created_owner.value for value in values]==[10,10,20,20,30,30]
    assert [value.lane_index() for value in values]==[0,1,0,1,0,1]
    widths=[8,9,8,9,13,14]
    assert [value.width() for value in values]==widths
    for value,width in zip(values,widths):
        value.mask.value=(1<<width)-1
        assert value.mask.value==(1<<width)-1
    values[3].update_owner(Int(25))
    assert [value.owner() for value in values]==[10,10,25,25,30,30]
    assert [cls.owner_index() for cls in types]==[10,11,25,26,30,31]
    assert [cls.inherited_owner() for cls in types]==[18,19,33,34,43,44]
    previous,total=svx.Output(),svx.Inout(5)
    values[3].advance(Int(12),previous,total)
    assert previous.value==4 and total.value==17 and values[3].status()==1038
    for name,value in zip(('a0','a1','b0','b1','c0','c1'),values):
        svx.publish_object('generate.'+name,value)
    svx.display('GENERATE_CLASSES_PYTHON_PASS')
