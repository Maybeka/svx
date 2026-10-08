from svtypes import AssocArray, Int, Queue

import svx
from svx import inheritance_class
from svx_mirror.field_pkg import Base
from tests.integration.field_projection_types import queue_of_int

released = False


@inheritance_class(
    canonical_id="py://tests/integration/field_projection/PythonLayer",
    constructor_initiator="sv",
)
class PythonLayer(Base):
    retry = Int()
    history = Queue[Int]()
    mapping = AssocArray[Int, Int]()

    def __init__(self, *constructor_args):
        if constructor_args != tuple(range(1, 9)):
            raise AssertionError("SV-origin constructor did not preserve declared parameter values")
        super().__init__(*constructor_args)
        if self.collisions(1, 2, 3, 4, 5, 6) != 21:
            raise AssertionError("instance mirror changed colliding parameter values")
        if self.collisions_static(1, 2, 3, 4, 5, 6) != 21:
            raise AssertionError("static mirror changed colliding parameter values")
        self.retry.value = 7
        if self.retry.value != 7:
            raise AssertionError("projected SvTypes field did not round-trip during Python initialization")
        history = self.history.value
        history.append(3)
        history.insert(0, 2)
        history[1] = 4
        if history.pop(0) != 2:
            raise AssertionError("projected SvTypes queue pop did not preserve the removed value")
        history.append(9)
        if isinstance(history, list):
            # Local SvTypes values are snapshots; projected values are live views.
            self.history.value = history
        if list(self.history.value) != [4, 9]:
            raise AssertionError("projected SvTypes queue operations did not round-trip")
        mapping = self.mapping.value
        mapping[1] = 6
        mapping[2] = 8
        del mapping[1]
        if isinstance(mapping, dict):
            self.mapping.value = mapping
        if dict(self.mapping.value) != {2: 8}:
            raise AssertionError("projected SvTypes associative updates did not round-trip")

    def _svx_release_projected_fields(self):
        global released
        super()._svx_release_projected_fields()
        released = True


@svx.export(name="field_projection.check_release")
def check_release():
    if not released:
        raise AssertionError("SV object release did not retire the Python projected-field binding")
    standalone = PythonLayer(*range(1, 9))
    assert isinstance(standalone.history.value, list)
    assert isinstance(standalone.mapping.value, dict)
    from svx.inheritance import close_instance
    close_instance(standalone._svx_remote_object_id)


@svx.export(name="field_projection.check_failed_release")
def check_failed_release():
    policy = svx.get_exception_policy()
    svx.set_exception_policy(svx.REPORT)
    try:
        _check_failed_release()
    finally:
        svx.set_exception_policy(policy)


def _check_failed_release():
    import gc
    import weakref

    from svx import _native
    from svx.inheritance import bind_instance, unbind_instance

    class FailingRelease:
        def _svx_release_projected_fields(self):
            raise ValueError("RELEASE_HOOK_FAILURE")

    class FailingLookup:
        @property
        def _svx_release_projected_fields(self):
            raise ValueError("RELEASE_LOOKUP_FAILURE")

    class ReentrantRelease:
        def _svx_release_projected_fields(self):
            assert _native.inheritance_get(9003) is None
            unbind_instance(9003)
            for object_id in range(9100, 9200):
                bind_instance(object_id, object())

    for object_id, cls, marker in (
        (9001, FailingRelease, "RELEASE_HOOK_FAILURE"),
        (9002, FailingLookup, "RELEASE_LOOKUP_FAILURE"),
        (9003, ReentrantRelease, None),
    ):
        instance = cls()
        retained = weakref.ref(instance)
        bind_instance(object_id, instance)
        del instance
        try:
            unbind_instance(object_id)
        except RuntimeError as error:
            if marker is None or marker not in str(error):
                raise
        else:
            if marker is not None:
                raise AssertionError("cleanup failure was silently discarded")
        assert _native.inheritance_get(object_id) is None
        gc.collect()
        assert retained() is None, "native registry retained a retired instance"
        unbind_instance(object_id)
        replacement = object()
        bind_instance(object_id, replacement)
        assert _native.inheritance_get(object_id) is replacement
        unbind_instance(object_id)

    for object_id in range(9100, 9200):
        unbind_instance(object_id)
    print("INHERITANCE_FAILED_RELEASE_PASS", flush=True)
