"""Owner-local types travel with the exported class, without extra selectors."""
import svx
from svx_mirror_instance.tb_instance_runtime_values.a.classes import Driver as DriverA, Mode as ModeA, Payload as PayloadA
from svx_mirror_instance.tb_instance_runtime_values.b.classes import Driver as DriverB, Mode as ModeB, Payload as PayloadB
from svx_mirror_instance.tb_instance_runtime_values.c.classes import Driver as DriverC, Mode as ModeC, Payload as PayloadC


class PythonDriver(DriverB):
    def echo(self, value):
        super().echo(value)
        return ModeB.ONE

    def echo_payload(self, value):
        result=super().echo_payload(value)
        result.data.value+=1
        return result

    def echo_packets(self, values):
        values=super().echo_packets(values)
        values[1].data.value+=2
        return values


@svx.export(name='instance_runtime_values.run')
def run():
    assert ModeA is not ModeB and ModeA is not ModeC
    for cls,mode,payload,width in (
        (DriverA,ModeA,PayloadA,8), (DriverB,ModeB,PayloadB,8), (DriverC,ModeC,PayloadC,13)
    ):
        value=cls(mode.ONE)
        assert value.mode.value==mode.ONE
        assert value.echo(mode.ZERO)==mode.ZERO
        packet=payload()
        packet.mode.value=mode.ONE
        packet.data.value=(1<<width)-1
        assert value.echo_payload(packet).data.value==(1<<width)-1
        value.payload.data.value=7
        assert value.payload.data.value==7
        returned=value.echo_packets([packet,packet])
        assert len(returned)==2 and returned[1].data.value==(1<<width)-1
        assert value.echo_modes([mode.ONE,mode.ZERO])==[1,0]
        assert cls.static_echo(mode.ONE)==mode.ONE
        previous,count=svx.Output(),svx.Inout(5)
        value.advance(mode.ZERO,previous,count)
        assert previous.value.data.value==7 and count.value==6
        assert value.mode.value==mode.ZERO
    svx.publish_object('b',PythonDriver(ModeB.ONE))
    svx.display('INSTANCE_RUNTIME_VALUES_PYTHON_PASS')
