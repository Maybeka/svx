"""Await must not return while newly forked children are still running."""

import svx


@svx.export(name='process.immediate_await')
def run():
    events = []

    def child(tag):
        events.append(('start', tag))
        svx.delay(1, 'ns')
        events.append(('done', tag))

    group = svx.fork_join_none((lambda: child(0), lambda: child(1)))
    group.await_()
    assert group.status() is svx.ProcessStatus.FINISHED, (group.status(), events)
    assert sorted(events) == [('done', 0), ('done', 1), ('start', 0), ('start', 1)]
    group.await_()
    completed_waiters = []
    target = svx.fork_join_none((lambda: svx.delay(1, 'ns'),))

    def wait_for_target(tag):
        target.await_()
        assert target.status() is svx.ProcessStatus.FINISHED
        completed_waiters.append(tag)

    waiters = svx.fork_join_none((lambda: wait_for_target(0), lambda: wait_for_target(1)))
    waiters.await_()
    assert sorted(completed_waiters) == [0, 1], completed_waiters
    target.await_()
    svx.display('SVX_IMMEDIATE_GROUP_AWAIT_PASS')
