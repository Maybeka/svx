"""Synchronous Python scenarios; SV owns all clock edges and pin activity."""

from __future__ import annotations

from dataclasses import dataclass

import svx

from .models import MigrationObservation, MigrationRequest, MigrationResponse


@dataclass(frozen=True)
class Operation:
    tag: int
    write: int
    address: int
    data: int


def program(count: int = 64, salt: int = 0) -> tuple[Operation, ...]:
    if count < 8:
        raise ValueError("a migration program needs at least eight transactions")
    return tuple(
        Operation(i, int(i >= 4 and (i < 8 or i % 3 != 0)), ((i * 3) % 4) * 4,
                  ((i * 0x01020304) ^ 0xA5A55A5A ^ salt) & 0xFFFFFFFF)
        for i in range(count)
    )


def expected_results(operations: tuple[Operation, ...]) -> tuple[int, ...]:
    registers = [0] * 4
    results = []
    for op in operations:
        if op.address not in (0, 4, 8, 12):
            raise ValueError(f"unmapped address: {op.address}")
        if op.write:
            registers[op.address // 4] = op.data
        results.append(registers[op.address // 4])
    return tuple(results)


def request_for(op: Operation) -> MigrationRequest:
    request = MigrationRequest()
    request.tag.value = op.tag
    request.stop.value = 0
    request.write.value = op.write
    request.address.value = op.address
    request.data.value = op.data
    return request


def run_program(operations: tuple[Operation, ...], *, check_monitor: bool = True) -> None:
    """Retain a narrow transaction boundary and drain both result streams."""
    bus = svx.reqrsp_channel("migration.bus", MigrationRequest, MigrationResponse)
    monitor = svx.mon_channel("migration.bus.mon", MigrationObservation)
    expected = expected_results(operations)
    counts = {"responses": 0, "observations": 0}

    def producer() -> None:
        for op, value in zip(operations, expected):
            response = bus.request(request_for(op))
            assert not response.stop.value and response.tag.value == op.tag, (
                f"MIGRATION_RESPONSE_ORDER tag={op.tag} got={response.tag.value}"
            )
            assert response.data.value == value, (
                f"MIGRATION_RESPONSE_MISMATCH tag={op.tag} address={op.address} "
                f"expected=0x{value:08x} actual=0x{response.data.value:08x}"
            )
            counts["responses"] += 1
        end = MigrationRequest()
        end.stop.value = 1
        assert bus.request(end).stop.value, "MIGRATION_BAD_RESPONSE_END"

    def observer() -> None:
        for op, value in zip(operations, expected):
            observation = monitor.get()
            actual = (observation.tag.value, observation.write.value,
                      observation.address.value, observation.data.value)
            assert not observation.stop.value and actual == (op.tag, op.write, op.address, value), (
                f"MIGRATION_MONITOR_MISMATCH tag={op.tag} expected="
                f"{(op.tag, op.write, op.address, value)!r} actual={actual!r}"
            )
            counts["observations"] += 1
        assert monitor.get().stop.value, "MIGRATION_BAD_MONITOR_END"

    if check_monitor:
        svx.fork_join([producer, observer])
    else:
        producer()
    assert counts["responses"] == len(operations)
    if check_monitor:
        assert counts["observations"] == len(operations)
        assert {op.address for op in operations} == {0, 4, 8, 12}
        assert {op.write for op in operations} == {0, 1}
        svx.display(f"MIGRATION_PY_SCOREBOARD_PASS count={counts['observations']} addresses=4 operations=2")
    svx.display(f"MIGRATION_PY_RESPONSES_PASS count={counts['responses']}")


@svx.test
def entry() -> None:
    svx.display("MIGRATION_PY_ENTRY_PASS")


@svx.test
def stimulus() -> None:
    run_program(program(), check_monitor=False)


@svx.test
def smoke() -> None:
    run_program(program())


@svx.test
def stress() -> None:
    run_program(program(4096, salt=0x12345678))
