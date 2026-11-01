"""Real-runtime package inheritance, field identity and virtual dispatch probe."""

import svx
from svx_mirror.export_base_pkg import Base
from svx_mirror.export_driver_pkg import Driver


class PythonDriver(Driver):
    def status(self):
        return super().status() + 100


@svx.export(name='package_export.run')
def run():
    assert issubclass(Driver, Base)
    item = PythonDriver(23)
    assert isinstance(item, Base)
    assert item.seed.value == 23
    assert int(item.status()) == 124
    assert int(Base.status(item)) == 23
    assert int(item.identity()) == 20
    assert int(Base.identity(item)) == 10
    previous, total = svx.Output(), svx.Inout(5)
    item.advance(previous, total)
    assert previous.value == 23 and total.value == 29
    assert item.seed.value == 24
    svx.publish_object('package_driver', item)
    svx.display('PACKAGE_EXPORT_PYTHON_PASS')
