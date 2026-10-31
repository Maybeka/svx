"""Use package APIs without merging their original compilation units."""
import svx
from svtypes import Int
from svx_mirror.unit_child_pkg import Child, WIDTH


class PythonChild(Child):
    def get(self):
        return super().get() + 100


@svx.export(name='sv_export.independent_units')
def run():
    assert WIDTH == 13
    item = PythonChild(Int(5))
    assert item.count.value == 5 and item.word.value == 5
    assert item.get() == 106
    previous, total = svx.Output(), svx.Inout(10)
    item.advance(Int(3), previous, total)
    assert previous.value == 5 and total.value == 18
    assert item.count.value == 8 and item.get() == 109
    item.word.value = 0x1234
    assert item.word.value == 0x1234
    svx.publish_object('export.units.child', item)
    svx.display('INDEPENDENT_UNITS_PYTHON_PASS')
