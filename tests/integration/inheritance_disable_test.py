import sys

import svx
from svx_mirror.inheritance_disable_pkg import Worker


class Derived(Worker):
    def hook(self, changed, observed):
        try:
            self.wait_value(changed, observed)
        finally:
            events.append("callback:" + type(sys.exc_info()[1]).__name__)
            if fail_finally:
                raise RuntimeError("EXPECTED_INHERITANCE_DISABLED_FINALLY_ERROR")


events = []
changed = None
observed = None
worker = None
callback = False
fail_finally = False


def blocked(static, through_callback=False):
    global changed, observed, worker
    changed = svx.Inout(10)
    observed = svx.Output()
    worker = Derived()
    try:
        method = (worker.wait_through_python if through_callback else
                  Worker.wait_static if static else worker.wait_value)
        method(changed, observed)
        events.append("completed")
    finally:
        events.append(type(sys.exc_info()[1]).__name__)


@svx.export(name="inheritance_disable.object")
def run_object():
    blocked(False)


@svx.export(name="inheritance_disable.static")
def run_static():
    blocked(True)


@svx.export(name="inheritance_disable.callback")
def run_callback():
    global callback
    callback = True
    blocked(False, True)


@svx.export(name="inheritance_disable.finally_error")
def run_finally_error():
    global callback, fail_finally
    callback = fail_finally = True
    blocked(False, True)


@svx.export(name="inheritance_disable.check")
def check():
    expected = (["callback:SVXCancellationError"] if callback else [])
    assert events == expected + ["SVXCancellationError"], events
    assert changed.value == 10, "disabled call performed inout copy-out"
    try:
        observed.value
    except svx.SVXInheritanceError:
        pass
    else:
        raise AssertionError("disabled call performed output copy-out")
    # A later non-disabled call in the same session must still succeed.
    method = worker.wait_through_python if callback else worker.wait_value
    method(changed, observed)
    assert changed.value == 15
    assert observed.value == 16
    svx.close_instance(worker._svx_remote_object_id)
    svx.display("SVX_INHERITANCE_DISABLE_PASS")
