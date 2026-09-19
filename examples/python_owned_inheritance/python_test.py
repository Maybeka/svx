import svx

from svx_py.examples.python_owned_inheritance.base_monitor import BaseMonitor


@svx.export(name="python-owned-inheritance.run")
def run():
    monitor = BaseMonitor(9)
    assert monitor.seed == 9
    assert monitor.sample() == 42
    monitor.notify()
    assert monitor.notified
    svx.display("Python-owned inheritance example passed")
