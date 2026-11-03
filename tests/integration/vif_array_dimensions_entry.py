"""Read and write unpacked interface arrays without changing packed shape."""
import svx
from svx_mirror.array_dimensions_pkg import Owner


@svx.export(name='array_dimensions.run')
def run():
    bus = Owner.get_bus()
    assert bus.read_values() == [1, 2, 3, 4]
    assert bus.read_vectors() == [[0x123456, 0x234567, 0x345678],
                                  [0x456789, 0x56789a, 0x6789ab]]
    bus.write_values([11, 22, 33, 44])
    expected = [[0xabcdef, 0x102030, 0x405060], [0x708090, 0xa0b0c0, 0xd0e0f0]]
    bus.write_vectors(expected)
    assert bus.read_values() == [11, 22, 33, 44]
    assert bus.read_vectors() == expected
    svx.display('VIF_ARRAY_DIMENSIONS_PYTHON_PASS')
