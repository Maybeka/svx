"""Concurrent waits must neither complete nor cancel unrelated invocations."""

import svx


@svx.export(name="wait_isolation.run")
def run():
    completed = []

    def fast():
        svx.delay(0.25, "ns")
        completed.append("fast")

    def slow():
        try:
            svx.delay(10, "ns")
            completed.append("slow")
        finally:
            completed.append("slow-cleanup")

    group = svx.fork_join_any([fast, slow])
    assert completed == ["fast"], completed
    group.kill()
    assert completed == ["fast", "slow-cleanup"], completed

    for operation in ("get_payload", "peek_payload"):
        for cancel in (False, True):
            values = {}
            prefix = f"isolation.{operation}.{cancel}"
            left, right = svx.channel(prefix + ".left"), svx.channel(prefix + ".right")

            def receive(channel, side):
                try:
                    values[side] = getattr(channel, operation)().data
                finally:
                    values[side + "-cleanup"] = True

            left_group = svx.fork_join_none([lambda: receive(left, "left")])
            right_group = svx.fork_join_none([lambda: receive(right, "right")])
            svx.delay(0.1, "ns")
            if cancel:
                left_group.kill()
                assert values == {"left-cleanup": True}, values
            else:
                left.put_payload(b"left")
                left_group.await_()
                assert values == {"left": b"left", "left-cleanup": True}, values
            right.put_payload(b"right")
            right_group.await_()
            assert values["right"] == b"right"
            assert values["right-cleanup"] is True
            if operation == "peek_payload":
                assert right.get_payload().data == b"right"
                if not cancel:
                    assert left.get_payload().data == b"left"
    svx.display("SVX_WAIT_ISOLATION_PASS")
