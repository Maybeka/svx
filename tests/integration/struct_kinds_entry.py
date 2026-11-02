"""Native struct-kind integration; requires the real SvTypes capability."""
import svx
from svtypes import LogicValue
from svx_mirror.struct_kinds_pkg import Driver


class PythonDriver(Driver):
    def transform(self, value):
        result = super().transform(value)
        result.label.value = 'python-callback'
        return result

    def exchange(self, value, previous, current):
        super().exchange(value, previous, current)
        current.value.label.value = 'task-callback'


@svx.export(name='struct_kinds.run')
def run():
    driver = Driver()
    original = driver.read()
    assert original.label.value == 'initial'
    assert original.header.tag.value == 0x12
    assert original.header.flags.value == LogicValue.from_string('10xz')
    assert original.gain.value == 1.5
    original.label.value = 'python'
    original.header.tag.value = 0x45
    assert driver.read().label.value == 'initial'
    echoed = driver.echo(original)
    assert echoed.label.value == 'python'
    echoed.label.value = 'copy'
    assert original.label.value == 'python'
    previous, current = svx.Output(), svx.Inout(driver.read())
    driver.exchange(original, previous, current)
    assert previous.value.label.value == 'initial'
    assert current.value.label.value == 'python'
    assert driver.read().label.value == 'python'
    driver.data.label.value = 'local-write'
    assert driver.read().label.value == 'local-write'
    assert driver.read().header.tag.value == 0x45
    driver.data.value = previous.value
    restored = driver.read()
    assert restored.label.value == 'initial'
    assert restored.header.flags.value == LogicValue.from_string('10xz')
    handles = driver.read_handles()
    first = handles.item.value
    assert first.object_number != 0
    assert handles.same_item.value == first
    assert driver.handles_match(handles)
    returned = driver.echo_handles(handles)
    assert returned.item.value == first and driver.handles_match(returned)
    child = PythonDriver()
    transformed = child.invoke_transform(original)
    assert transformed.label.value == 'python-callback'
    assert original.label.value == 'python'
    previous, current = svx.Output(), svx.Inout(child.read())
    child.invoke_exchange(original, previous, current)
    assert previous.value.label.value == 'initial'
    assert current.value.label.value == 'task-callback'
    svx.display('STRUCT_KINDS_PYTHON_PASS')
