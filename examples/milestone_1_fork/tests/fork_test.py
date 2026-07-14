import svx


def child_a():
    svx.display("fork_join child_a start")
    svx.delay(1.0, "ns")
    svx.display("fork_join child_a done")


def child_b():
    svx.display("fork_join child_b start")
    svx.delay(2.0, "ns")
    svx.display("fork_join child_b done")


def any_fast():
    svx.display("fork_join_any fast start")
    svx.delay(0.5, "ns")
    svx.display("fork_join_any fast done")


def any_slow():
    svx.display("fork_join_any slow start")
    svx.delay(3.0, "ns")
    svx.display("fork_join_any slow done")


def background():
    svx.display("fork_join_none background start")
    svx.delay(1.25, "ns")
    svx.display("fork_join_none background done")


@svx.export
def main():
    svx.display("fork test start")

    svx.display("before fork_join")
    svx.fork_join([child_a, child_b])
    svx.display("after fork_join")

    svx.display("before fork_join_any")
    group_any = svx.fork_join_any([any_fast, any_slow])
    svx.display(f"after fork_join_any status={group_any.status().value}")
    group_any.kill()
    svx.display(f"after fork_join_any kill status={group_any.status().value}")

    svx.display("before fork_join_none")
    group_none = svx.fork_join_none([background])
    svx.display(f"after fork_join_none status={group_none.status().value}")
    group_none.await_()
    svx.display(f"after fork_join_none await status={group_none.status().value}")

    svx.display("fork test done")
