import svx
from svx_mirror.constructor_defaults_pkg import Driver


@svx.export(name='constructor_defaults.run')
def run():
    value = Driver(21, 'python-driver')
    assert value.get_seed() == 21
    assert value.get_label() == 'python-driver'
    value.advance(2)
    assert value.get_seed() == 23
    svx.close_instance(value)
    svx.display('CONSTRUCTOR_DEFAULTS_PYTHON_PASS')
