"""Class-owned values retain native storage inside their generate owner."""
import svx
from svtypes import LogicValue
from svx_mirror_instance.tb_generate_runtime_values.a.svx_scope_4_lane_p0.classes import Driver as DriverA
from svx_mirror_instance.tb_generate_runtime_values.b.svx_scope_4_lane_p0.classes import Driver as DriverB


class PythonDriver(DriverB):
    def echo(self, value):
        super().echo(value)
        return self.Mode.ONE

    def echo_payload(self, value):
        result = super().echo_payload(value)
        assert not (result.data.value.x_mask | result.data.value.z_mask)
        result.data.value = result.data.value.value_mask + 1
        return result

    def echo_packets(self, values):
        result = super().echo_packets(values)
        assert not (result[1].data.value.x_mask | result[1].data.value.z_mask)
        result[1].data.value = result[1].data.value.value_mask + 2
        return result


@svx.export(name="generate_runtime_values.run")
def run():
    assert DriverA.Mode is not DriverB.Mode
    assert DriverA.Payload is not DriverB.Payload
    for cls, width in ((DriverA, 8), (DriverB, 13)):
        mode, payload = cls.Mode, cls.Payload
        value = cls(mode.ONE)
        assert value.mode.value == mode.ONE
        assert value.echo(mode.ZERO) == mode.ZERO
        packet = payload()
        packet.mode.value = mode.ONE
        packet.data.value = LogicValue(width, 1, 2, 4)
        assert value.echo_payload(packet).data.value == packet.data.value

        value.payload.mode.value = mode.ZERO
        observed = value.current_payload()
        assert observed.mode.value == mode.ZERO
        assert observed.data.value == packet.data.value
        value.payload.data.value = 7

        value.modes.value = [mode.ONE, mode.ZERO]
        value.modes.value[1] = mode.ONE
        value.modes.value.append(mode.ZERO)
        assert list(value.current_modes()) == [1, 1, 0]

        value.packets.value = [packet, packet]
        value.packets.value[0].data.value = 9
        value.packets.value[0].mode.value = mode.ZERO
        observed = value.current_packets()
        assert observed[0].data.value == LogicValue(width, 9)
        assert observed[0].mode.value == mode.ZERO
        assert observed[1].data.value == packet.data.value
        assert observed[1].mode.value == mode.ONE

        value.samples.value = [packet, packet]
        value.samples.value[1].mode.value = mode.ZERO
        observed = value.current_samples()
        assert len(observed) == 2 and observed[1].mode.value == mode.ZERO
        assert observed[0].data.value == packet.data.value

        value.by_name.value = {"first": packet, "last": packet}
        value.by_name.value["first"].data.value = 11
        observed = value.current_by_name()
        assert observed["first"].data.value == LogicValue(width, 11)
        assert observed["last"].data.value == packet.data.value

        value.groups.value = {"left": [packet, packet], "empty": []}
        value.groups.value["left"][1].mode.value = mode.ZERO
        observed = value.current_groups()
        assert list(observed["empty"]) == []
        assert observed["left"][0].mode.value == mode.ONE
        assert observed["left"][1].mode.value == mode.ZERO
        assert observed["left"][1].data.value == packet.data.value

        assert cls.static_echo(mode.ONE) == mode.ONE
        previous, count = svx.Output(), svx.Inout(5)
        value.advance(mode.ZERO, previous, count)
        assert previous.value.data.value == LogicValue(width, 7)
        assert count.value == 6 and value.mode.value == mode.ZERO
    svx.publish_object("generate_driver", PythonDriver(DriverB.Mode.ONE))
    svx.display("GENERATE_RUNTIME_VALUES_PYTHON_PASS")
