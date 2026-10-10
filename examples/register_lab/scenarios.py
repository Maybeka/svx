"""Scenario/scoreboard code; the SV side owns all bus timing and sampling."""

import svx
from svtypes import LogicValue

from .models import RegisterObservation, RegisterRequest, RegisterResponse
from .signals import cookie, read_data, status
from .extensions import check_handles, close_policy, policy


def request(tag, write, address, data=0):
    item = RegisterRequest()
    item.tag.value = tag
    item.write.value = int(write)
    item.address.value = address
    item.data.value = data
    return item


def program():
    values = [0x10203040, 0x55667788, 0xA5A55A5A, 0xDEADBEEF]
    return [request(index + 1, True, index * 4, value)
            for index, value in enumerate(values)] + [
        request(index + 5, False, index * 4) for index in range(4)
    ]


def check_signals():
    assert cookie.read() == 0
    cookie.write(0x1234)
    assert cookie.read() == 0x1234
    cookie.force(0x5678)
    try:
        svx.delay(0.25, "ns")
        assert cookie.read() == 0x5678
    finally:
        cookie.release()
    cookie.write(0x1234)
    assert cookie.read() == 0x1234
    assert status.read() == LogicValue.from_string("10xz01z0")
    status.write(LogicValue.from_string("zx10xz01"))
    assert status.read() == LogicValue.from_string("zx10xz01")
    svx.display("REGISTER_LAB_SIGNALS_PASS")


def check_processes():
    shared = {"ticks": 0, "stopped": False}

    def watchdog():
        try:
            while True:
                svx.delay(0.25, "ns")
                shared["ticks"] += 1
        finally:
            shared["stopped"] = True

    group = svx.fork_join_none([watchdog])
    svx.delay(1, "ns")
    assert shared["ticks"] > 0
    group.kill()
    assert shared["stopped"]

    completed = []

    def quick():
        svx.delay(0.25, "ns")
        completed.append("quick")

    def slow():
        svx.delay(10, "ns")
        completed.append("slow")

    race = svx.fork_join_any([quick, slow])
    assert completed == ["quick"], f"race completed={completed!r}, status={race.status()}"
    race.kill_running()
    race.await_()
    svx.display("REGISTER_LAB_PROCESSES_PASS")


def check_independent_waits():
    for operation in ("get_payload", "peek_payload"):
        completed = {}
        left = svx.channel(f"lab.wait.{operation}.left")
        right = svx.channel(f"lab.wait.{operation}.right")

        def receive(channel, side):
            completed[side] = getattr(channel, operation)().data

        left_group = svx.fork_join_none([lambda: receive(left, "left")])
        right_group = svx.fork_join_none([lambda: receive(right, "right")])
        svx.delay(0.1, "ns")
        left.put_payload(b"left")
        left_group.await_()
        assert completed == {"left": b"left"}, completed
        right.put_payload(b"right")
        right_group.await_()
        assert completed == {"left": b"left", "right": b"right"}, completed
        if operation == "peek_payload":
            assert left.get_payload().data == b"left"
            assert right.get_payload().data == b"right"
    svx.display("REGISTER_LAB_INDEPENDENT_WAITS_PASS")


def check_bus():
    from svx_py.examples.register_lab.extensions import Checker

    checker = Checker(42)
    assert checker.seed == 42
    bus = svx.reqrsp_channel("lab.bus", RegisterRequest, RegisterResponse)
    monitor = svx.mon_channel("lab.bus.mon", RegisterObservation)
    commands = program()
    expected = {}
    mirror = {}
    seen = []

    def producer():
        for item in commands:
            address = item.address.value
            if item.write.value:
                mirror[address] = item.data.value
            value = policy().normalize(mirror[address])
            expected[item.tag.value] = (address, item.write.value, value)
            response = bus.request(item)
            assert response.tag.value == item.tag.value
            assert checker.compare(value, response.data.value), (
                f"REGISTER_LAB_MISMATCH tag={item.tag.value} "
                f"expected=0x{value:08x} actual=0x{response.data.value:08x}"
            )

    def observer():
        for _ in commands:
            item = monitor.get()
            assert (item.address.value, item.write.value, item.data.value) == expected[item.tag.value], (
                f"REGISTER_LAB_MISMATCH monitor tag={item.tag.value} "
                f"expected={expected[item.tag.value]} actual=0x{item.data.value:08x}"
            )
            seen.append(item.tag.value)

    svx.fork_join([producer, observer])
    assert seen == list(range(1, 9))
    assert checker.python_calls == 8
    checker.finish()
    assert checker.finished
    svx.close_instance(checker)
    svx.display("REGISTER_LAB_CHECKER_PASS")
    svx.display("REGISTER_LAB_BUS_PASS transactions=8 observations=8")


def check_raw_trace():
    sent = bytes.fromhex("53565800017fff")
    empty = svx.channel("lab.empty")
    assert empty.try_get_payload() is None
    svx.channel("lab.trace.req").put_payload(sent)
    channel = svx.channel("lab.trace.rsp")
    assert channel.peek_payload().data == sent
    assert channel.get_payload().data == sent
    svx.display("REGISTER_LAB_PAYLOAD_PASS")


@svx.test
def smoke():
    check_signals()
    check_processes()
    check_independent_waits()
    check_handles()
    check_bus()
    check_raw_trace()
    completed = {svx.channel("lab.env.done").get_payload().data for _ in range(3)}
    assert completed == {b"driver", b"monitor", b"trace"}, completed
    close_policy()
    svx.display("REGISTER_LAB_PYTHON_PASS")


@svx.test
def corrupt_read():
    read_data.force(LogicValue(32, 0))
    try:
        check_bus()
    finally:
        read_data.release()
    raise AssertionError("fault injection unexpectedly passed")


@svx.test
def function_wait():
    from . import extensions
    from svx_py.examples.register_lab.extensions import Checker

    checker = Checker(42)
    extensions.delay_in_compare = True
    checker.compare(0, 0)
    raise AssertionError("function callback delay unexpectedly succeeded")
