"""Use the exact native owner selected by the original project hierarchy."""
import svx
from svtypes import Int
from svx_mirror_instance.tb_instance_classes.a.classes import Driver as DriverA
from svx_mirror_instance.tb_instance_classes.b.classes import Driver as DriverB
from svx_mirror_instance.tb_instance_classes.c.classes import Driver as DriverC


class PythonDriver(DriverB):
    def status(self):
        return super().status()+1000


@svx.export(name='instance_classes.run')
def run():
    a,b,c=DriverA(Int(3)),PythonDriver(Int(7)),DriverC(Int(5))
    assert [value.created_owner.value for value in (a,b,c)]==[10,20,30]
    assert [value.owner() for value in (a,b,c)]==[10,20,30]
    assert [value.width() for value in (a,b,c)]==[8,8,13]
    assert [value.mask.width for value in (a,b,c)]==[8,8,13]
    c.mask.value=0x1fff
    assert c.mask.value==0x1fff and a.mask.value==0 and b.mask.value==0
    b.update_owner(Int(25))
    assert [value.owner() for value in (a,b,c)]==[10,25,30]
    assert [DriverA.read_owner(),DriverB.read_owner(),DriverC.read_owner()]==[10,25,30]
    assert [DriverA.inherited_owner(),DriverB.inherited_owner(),DriverC.inherited_owner()]==[18,33,43]
    previous,total=svx.Output(),svx.Inout(5)
    b.advance(Int(12),previous,total)
    assert previous.value==7 and total.value==17 and b.status()==1037
    for name,value in (('a',a),('b',b),('c',c)):
        svx.publish_object('instance.'+name,value)
    svx.display('INSTANCE_CLASSES_PYTHON_PASS')
