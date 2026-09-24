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
    response = monitor.transfer(5, 10)
    assert response.changed.value == 15
    assert response.observed.value == 24
    response = monitor.calculate(4, 10)
    assert response.changed.value == 14
    assert response.observed.value == 23
    assert response.result.value == 24
