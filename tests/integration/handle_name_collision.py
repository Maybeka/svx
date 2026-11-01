import svtypes
import svx

from svx_mirror.collision_api import Owner


class Derived(Owner):
    def echo_left(self, value):
        self.callback_count += 1
        return super().echo_left(value)


instance = None


@svx.export(name='handle_collision.run')
def run():
    global instance
    left = Owner.make_left(11)
    right = Owner.make_right(22)
    assert left.target_type_name == 'sv://a_b/C'
    assert right.target_type_name == 'sv://a/b_C'
    assert left.object_number != right.object_number
    instance = Derived(left, right)
    instance.callback_count = 0
    assert instance.left.value == left
    assert instance.right.value == right
    assert instance.read_left(instance.echo_left(left)) == 11
    assert instance.read_right(instance.echo_right(right)) == 22
    instance.left_items.value = [left, svtypes.RemoteRefValue(left.target_type_name, 0), left]
    instance.right_items.value = [right, svtypes.RemoteRefValue(right.target_type_name, 0), right]
    left_items = list(instance.left_items.value)
    right_items = list(instance.right_items.value)
    assert instance.echo_left_items(left_items) == left_items
    assert instance.echo_right_items(right_items) == right_items
    assert left_items[0] == left_items[2] == left
    assert right_items[0] == right_items[2] == right
    assert left_items[1].object_number == right_items[1].object_number == 0
    wrong_kind = svtypes.RemoteRefValue(left.target_type_name, right.object_number)
    try:
        instance.left_items.value[0] = wrong_kind
    except svtypes.ExternalStorageError:
        pass
    else:
        raise AssertionError('a different native handle type passed the endpoint cast')
    assert list(instance.left_items.value) == left_items
    svx.publish_object('handle_collision.instance', instance)
    svx.display('HANDLE_NAME_COLLISION_PYTHON_PASS')


@svx.export(name='handle_collision.verify')
def verify():
    assert instance.callback_count == 2
    svx.display('HANDLE_NAME_COLLISION_CALLBACK_PASS')
