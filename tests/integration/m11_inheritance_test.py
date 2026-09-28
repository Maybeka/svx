import svx
from svx import Inout, Output
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
    changed = Inout(10)
    observed = Output()
    assert monitor.transfer(5, changed, observed) is None
    assert changed.value == 15
    assert observed.value == 24
    changed = Inout(10)
    observed = Output()
    assert monitor.calculate(4, changed, observed) == 24
    assert changed.value == 14
    assert observed.value == 23
