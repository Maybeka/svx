"""Source declarations: discovery resolves the empty SV mirror stub."""

import svx
from svtypes import Bit, Int, ExternalStorageError

delay_in_compare = False


@svx.sv_mirror("sv://register_policy_pkg/RegisterPolicy")
class RegisterPolicyStub(svx.SVMirror):
    pass


@svx.inheritance_class()
class PythonPolicy(RegisterPolicyStub):
    local_checks = Int()

    def __init__(self, mask: Bit[32]):
        super().__init__(mask)
        self.local_checks.value = 0

    @svx.inheritance_method
    def normalize(self, value: Bit[32]) -> svx.Function[Bit[32]]:
        self.calls.value += 1
        self.local_checks.value += 1
        self.history.push_back(self.calls.value)
        return super().normalize(value)

    @svx.inheritance_method
    def calibrate(self, delta: Int, observed: svx.Output[Int],
                  budget: svx.Inout[Int]) -> svx.Function[Int]:
        result = super().calibrate(delta, observed, budget)
        observed.value += 1
        budget.value += 2
        return result + 3


@svx.inheritance_class()
class Checker:
    def __init__(self, seed: Int):
        self.seed = seed
        self.python_calls = 0
        self.finished = False

    @svx.inheritance_method
    def compare(self, expected: Bit[32], actual: Bit[32]) -> svx.Function[Bit[1]]:
        if delay_in_compare:
            svx.delay(1, "ns")
        self.python_calls += 1
        return int(expected == actual)

    @svx.inheritance_method
    def finish(self) -> svx.Task:
        svx.delay(0.05, "ns")
        self.finished = True


_policy = None


def policy():
    assert _policy is not None, "the SV testbench must run register_lab.create_policy first"
    return _policy


@svx.export(name="register_lab.create_policy")
def create_policy():
    global _policy
    _policy = PythonPolicy(0xFFFFFFFF)
    observed, budget = svx.Output(), svx.Inout(5)
    assert _policy.calibrate(2, observed, budget) == 10
    assert observed.value == 3 and budget.value == 9
    assert _policy.word_bytes() == 4
    svx.publish_object("register_lab.policy", _policy)
    svx.display("REGISTER_LAB_POLICY_CREATED")


def check_handles():
    receiver = policy()
    packet = receiver.packet.value
    assert receiver.echo_packet(packet).object_number == packet.object_number
    assert packet.target_type_name == "sv://register_policy_pkg/PacketTag"
    assert not hasattr(packet, "number"), "unmapped class handles must stay opaque"
    view = receiver.echo_bus(receiver.bus.value)
    assert receiver.same_bus(view), "the returned VIF must still identify the native bus"
    assert view.read_data() == view.read_rdata()
    assert not hasattr(view, "write_rdata"), "the diagnostics modport must stay read-only"
    assert not hasattr(view, "write_wdata"), "the driver is not exposed by this modport"
    svx.display("REGISTER_LAB_HANDLES_PASS")


def close_policy():
    receiver = policy()
    assert receiver.calls.value == 16
    assert receiver.local_checks.value == 16
    assert list(receiver.history.value) == list(range(1, 17))
    svx.close_instance(receiver)
    assert receiver.local_checks.value == 16
    try:
        receiver.calls.value
    except ExternalStorageError as error:
        assert "closed" in str(error.__cause__).lower(), str(error.__cause__)
    else:
        raise AssertionError("closed SV-resident storage stayed readable")
    svx.display("REGISTER_LAB_POLICY_CLOSE_PASS")
