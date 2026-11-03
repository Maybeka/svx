import svx
from svx_mirror.editable_static_pkg import Driver, package_scale


@svx.export(name='editable_static.run')
def run():
    assert int(Driver.scale(7)) == 21
    assert int(Driver.svx_core_Driver_scale()) == 99
    assert int(package_scale(7)) == 35
    Driver.wait_once()
    svx.display('EDITABLE_STATIC_PYTHON_PASS')
