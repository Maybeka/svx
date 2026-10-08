import svx
import svtypes
from svx import inheritance
from svx_mirror.natural_bridge_pkg import A
from tests.integration.natural_constructor_bridge_schema import PY_ID, SV_ID

events = []
instances = []
failed_instance = None


class B(A):
    __svx_root_field_ids__ = {}
    local_value = svtypes.Int()
    fail_after_super = False

    def __init__(self, seed, label, packet, bias=0):
        global failed_instance
        events.append(("before", seed, label))
        super().__init__(label=label + "-B", seed=seed + bias + 1, packet=packet)
        assert self.count.value == seed + bias + 1
        self.count.value += 100
        self.local_value.value = seed + 200
        if self.fail_after_super:
            failed_instance = self
            raise ValueError("natural B initialization failed after super")
        self.received = packet
        events.append(("after", self._svx_remote_object_id))
        instances.append(self)


class CView(B):
    __svx_foreign_class_id__ = "sv://natural_bridge_pkg/C"


@svx.export(name="natural_bridge.setup")
def setup():
    contract = inheritance._constructor_contracts[SV_ID]
    inheritance.register_constructor(PY_ID, contract.request_fields)
    inheritance.register_python_subclass(PY_ID, B)
    inheritance.register_constructor(CView.__svx_foreign_class_id__, contract.request_fields)
    inheritance.register_python_subclass(CView.__svx_foreign_class_id__, CView)


@svx.export(name="natural_bridge.verify")
def verify():
    assert len(instances) == 2
    assert all(isinstance(instance, B) for instance in instances)
    assert type(instances[0]) is CView
    assert type(instances[1]) is B
    first_id, second_id = [instance._svx_remote_object_id for instance in instances]
    assert first_id != second_id
    assert events == [("before", 17, "alpha-C"), ("after", first_id),
                      ("before", 17, "beta"), ("after", second_id)]
    assert svx._native.inheritance_get(first_id) is instances[0]
    assert svx._native.inheritance_get(second_id) is instances[1]
    assert instances[0].received == instances[1].received
    assert instances[0].received.target_type_name == "sv://natural_bridge_pkg/Packet"
    assert [instance.count.value for instance in instances] == [1118, 118]
    assert [instance.local_value.value for instance in instances] == [217, 217]
    assert inheritance._natural_constructor_segments.pending_count == 0
    assert first_id not in inheritance._reserved_python_receivers
    assert second_id not in inheritance._reserved_python_receivers
    assert all(instance._svx_initialized_python_portions == {PY_ID} for instance in instances)
    print("NATURAL_CONSTRUCTOR_NATIVE_PASS", flush=True)


@svx.export(name="natural_bridge.verify_planned")
def verify_planned():
    from svx_mirror.natural_bridge_child_pkg import C

    assert len(instances) == 1
    instance = instances[0]
    assert isinstance(instance, C)
    assert events == [("before", 17, "alpha-C"), ("after", instance._svx_remote_object_id)]
    assert svx._native.inheritance_get(instance._svx_remote_object_id) is instance
    assert instance.count.value == 1120
    assert instance.local_value.value == 217
    assert inheritance._natural_constructor_segments.pending_count == 0
    assert instance._svx_remote_object_id not in inheritance._reserved_python_receivers
    print("NATURAL_PLANNED_PYTHON_PASS", flush=True)


@svx.export(name="natural_bridge.fail_planned")
def fail_planned():
    original = svx.SVMirror._svx_retire_failed_python_companion
    checked = set()

    def verify_retirement(instance, error):
        original(instance, error)
        if (instance is not failed_instance or id(instance) in checked
                or inheritance._natural_constructor_segments.pending_count):
            return
        object_id = instance._svx_remote_object_id
        assert svx._native.inheritance_get(object_id) is None
        assert object_id not in inheritance._reserved_python_receivers
        for field in (instance.count, instance.local_value):
            try:
                _ = field.value
            except svtypes.ExternalStorageError:
                pass
            else:
                raise AssertionError("failed natural receiver retained live field storage")
        assert str(error) == "natural B initialization failed after super"
        checked.add(id(instance))
        print("NATURAL_ROLLBACK_PYTHON_PASS", flush=True)

    svx.SVMirror._svx_retire_failed_python_companion = verify_retirement
    B.fail_after_super = True
