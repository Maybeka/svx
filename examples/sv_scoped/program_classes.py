"""Call program-local classes through the ordinary mirror interface."""
import svx
from svtypes import Int
from svx_mirror_instance.tb_program_classes.a.classes import Driver as DriverA
from svx_mirror_instance.tb_program_classes.b.classes import Driver as DriverB
from svx_mirror_instance.tb_program_classes.c.classes import Driver as DriverC


class PythonDriver(DriverB):
    def status(self):
        return super().status()+1000


@svx.export(name='program_classes.run')
def run():
    for cls,value in ((DriverA,10),(DriverB,20),(DriverC,30)):
        cls.configure(Int(value))
    a,b,c=DriverA(Int(3)),PythonDriver(Int(7)),DriverC(Int(5))
    assert [value.created_owner.value for value in (a,b,c)]==[10,20,30]
    assert [value.width() for value in (a,b,c)]==[8,8,13]
    c.mask.value=0x1fff
    assert c.mask.value==0x1fff and a.mask.value==0 and b.mask.value==0
    b.update_owner(Int(25))
    assert [cls.read_owner() for cls in (DriverA,DriverB,DriverC)]==[10,25,30]
    assert [cls.inherited_owner() for cls in (DriverA,DriverB,DriverC)]==[18,33,43]
    previous,total=svx.Output(),svx.Inout(5)
    b.advance(Int(12),previous,total)
    assert previous.value==7 and total.value==17 and b.status()==1037
    for name,value,expected,original in (('a',a,13,10),('b',b,1037,20),('c',c,35,30)):
        svx.publish_object('program.'+name,value)
        cls=(DriverA if name=='a' else DriverB if name=='b' else DriverC)
        cls.verify_published('program.'+name,Int(expected),Int(original))
    svx.display('PROGRAM_CLASSES_PYTHON_PASS')
