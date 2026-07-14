import svx
from svx_py.tests.integration.m11_base import BaseMonitor

monitor = None


@svx.export(name="m11.run")
def run():
    global monitor
    monitor = BaseMonitor(9)
    assert monitor.seed == 9
    assert monitor.sample() == 42
    monitor.notify()
    assert monitor.notified


@svx.export(name="m11.after_shutdown")
def after_shutdown():
    try:
        monitor.sample()
    except RuntimeError as error:
        assert "unknown SVX inheritance object id" in str(error)
    else:
        raise AssertionError("shutdown SVX inheritance object remained dispatchable")
