import gc
import weakref

import svx

events: list[str] = []


class _Sentinel:
    pass


def _child() -> None:
    svx.delay(5, "ns")
    events.append("done")


def _shutdown_child() -> None:
    try:
        svx.delay(100, "ns")
    finally:
        # Registries must remain usable until child cleanup has returned.
        svx.channel("shutdown-cleanup").put_payload(svx.Payload(b"done"))
        events.append("finally")
        svx.display("SVX_PROCESS_SHUTDOWN_CLEANUP_PASS")


def _immediate_child() -> None:
    pass


@svx.export(name="process_lifetime.run")
def run() -> None:
    sentinel = _Sentinel()
    reference = weakref.ref(sentinel)

    def held_child(held=sentinel) -> None:
        assert held is not None
        _child()

    group = svx.fork_join_none((held_child,))
    del group, held_child, sentinel
    gc.collect()
    assert reference() is not None, "active child state was released"
    svx.delay(10, "ns")
    assert events == ["done"], events
    for _ in range(32):
        group = svx.fork_join_any((_immediate_child, _child))
        assert reference() is None, "completed orphan callable was retained"
        del group
        gc.collect()
        svx.delay(6, "ns")
    assert events == ["done"] * 33, events
    # Trigger reclamation of the completed orphan at the next fork boundary.
    group = svx.fork_join_none((_shutdown_child,))
    del group
    gc.collect()
    svx.display("SVX_PROCESS_LIFETIME_PASS")
