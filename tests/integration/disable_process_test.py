import svx


events: list[str] = []


def _blocked_child() -> None:
    try:
        svx.delay(100, "ns")
        events.append("delay-completed")
    finally:
        events.append("finally")


def _blocked_channel_child() -> None:
    try:
        svx.channel("disable-process-channel").get_payload()
        events.append("channel-completed")
    finally:
        events.append("channel-finally")


@svx.export(name="disable_process.run")
def run() -> None:
    group = svx.fork_join_none((_blocked_child,))
    svx.delay(10, "ns")
    group.kill()
    if group.status().value != "killed":
        raise AssertionError(f"expected killed status, got {group.status()}")
    group.await_()
    if events != ["finally"]:
        raise AssertionError(f"cancelled process did not unwind normally: {events!r}")

    events.clear()
    group = svx.fork_join_none((_blocked_channel_child,))
    svx.delay(10, "ns")
    group.kill()
    group.await_()
    if events != ["channel-finally"]:
        raise AssertionError(f"cancelled channel wait did not unwind normally: {events!r}")

    svx.delay(1, "ns")
    svx.display("SVX_DISABLE_PROCESS_PASS")
