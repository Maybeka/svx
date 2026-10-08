"""Real native owner/storage checks for the internal root-proxy constructor."""

import svx
from svtypes import Bit, Enum, Int, Real, ShortReal, String, SvObject, constraint, rand_layer, svobj
from svtypes.errors import ExternalStorageError
from svx import _native
from svx.inheritance import create_python_instance, encode_constructor
from tests.integration.python_root_proxy_schema import ROOT_ID, DERIVED_ID

print("PYTHON_ROOT_PROXY_SOURCE_LOADED", flush=True)

failed_owner = None
constructed_roots = []
constructed_plains = []


@svx.export(name="python_root.check_autoload")
def check_autoload():
    import sys

    assert not constructed_roots
    assert not constructed_plains
    assert "svx_py.tests.integration.python_root_proxy_test" in sys.modules
    assert "svx_py.tests.integration.python_root_derived" in sys.modules
    assert "svx_mirror.python_root_probe_pkg" in sys.modules
    assert "tests.integration.python_root_final" not in sys.modules
    print("PYTHON_ROOT_PROXY_AUTOLOAD_PASS", flush=True)


class RootPolicyMode(Enum[Bit[8]]):
    ROOT_IDLE = 0
    ROOT_ACTIVE = 7


class PlainRoot:
    def __init__(self, seed):
        constructed_plains.append(self)
        self.seed = seed

    def check(self, delta):
        return self.seed + delta


plain_id = None


@svx.export(name="python_root.check_plain")
def check_plain():
    global plain_id
    for object_id in range(1, 10):
        instance = _native.inheritance_get(object_id)
        if isinstance(instance, PlainRoot):
            plain_id = object_id
            assert instance._svx_remote_object_id == object_id
            assert instance.check(3) == 16
            assert PlainRoot(8).check(3) == 11
            return
    raise AssertionError("plain Python root companion was not constructed")


@svx.export(name="python_root.check_plain_release")
def check_plain_release():
    assert _native.inheritance_get(plain_id) is None
    print("PYTHON_ROOT_PROXY_PLAIN_PASS", flush=True)


@svx.inheritance_class(canonical_id=ROOT_ID, constructor_initiator="sv")
@svobj
class Root(SvObject):
    count = Int()
    cycle = Bit[2](randc=True)
    local = Int()
    label = String('quoted "value"\\path\n')
    real_value = Real(2.5)
    short_value = ShortReal(-1.25)
    mode = RootPolicyMode(RootPolicyMode.ROOT_ACTIVE)

    @constraint
    def legal_count(self):
        self.count >= 0
        self.count <= 127

    @rand_layer(5)
    def cycle_layer(self):
        self.cycle

    def pre_randomize(self):
        if getattr(self, '_test_random_hooks', False):
            self._record_random_hook('pre')

    def post_randomize(self):
        if getattr(self, '_test_random_hooks', False):
            self._record_random_hook('post')

    def _record_random_hook(self, kind):
        assert _native.inheritance_get(self._svx_remote_object_id) is self
        child = getattr(self, 'child_value', None)
        assert self.check(0) == self.count.value + (child.value if child is not None else 0)
        self._test_hook_events.append((kind, self.svtypes_layered_randomize_active(),
                                      self.svtypes_layered_randomize_priority(), self.count.value))

    def __init__(self, seed: Int):
        global failed_owner
        constructed_roots.append(self)
        super().__init__()
        assert self.count.value == 0
        assert self.label.value == 'quoted "value"\\path\n'
        assert self.real_value.value == 2.5
        assert self.short_value.value == -1.25
        assert self.mode.value == RootPolicyMode.ROOT_ACTIVE
        self.count.value = seed
        self.local.value = 7
        if seed == 75:
            from svx_mirror.python_root_probe_pkg import Child

            nested = Child(13)
            assert nested.observed_value() == 13 and nested.check(1) == 114
            assert nested._svx_remote_object_id != self._svx_remote_object_id
            svx.close_instance(nested._svx_remote_object_id)
            assert self.count.value == 75
        if seed == 99:
            failed_owner = self
            raise ValueError("root initializer failure after SV write")

    def check(self, delta):
        return self.count.value + delta

    def fixed(self, delta):
        return self.count.value + delta + 200

    @staticmethod
    def scale(delta):
        return delta * 3

    @staticmethod
    def wait_once():
        svx.delay(1, "ns")


retained = None
retained_id = None
child_owner = None
child_field = None
child_id = None
derived_owner = None
derived_field = None


@svx.export(name="python_root.check_child_owner")
def check_child_owner():
    global child_owner, child_field, child_id
    candidates = []
    for object_id in range(1, 10):
        instance = _native.inheritance_get(object_id)
        if isinstance(instance, Root):
            candidates.append((object_id, instance))
    assert len(candidates) == 1, "SV child construction created more than one root companion"
    child_id, child_owner = candidates[0]
    assert child_owner._svx_remote_object_id == child_id
    assert child_owner.count.value == 53
    assert child_owner.local.value == 7
    child_field = child_owner.count
    child_field.value = 54
    # A later Python-facing method must not intercept an explicit SV super call
    # back into the original root portion.
    child_owner.check = lambda delta: 999
    assert child_owner.check(1) == 999


@svx.export(name="python_root.check_child_release")
def check_child_release():
    assert _native.inheritance_get(child_id) is None
    try:
        _ = child_field.value
    except ExternalStorageError:
        pass
    else:
        raise AssertionError("SV child release left the root field active")
    assert child_owner.local.value == 7
    print("PYTHON_ROOT_PROXY_SV_CHILD_PASS", flush=True)


@svx.export(name="python_root.check_python_origin_child")
def check_python_origin_child():
    from svx_mirror.python_root_probe_pkg import Child

    before = len(constructed_roots)
    value = Child(59)
    assert len(constructed_roots) == before + 1 and constructed_roots[-1] is value
    object_id = value._svx_remote_object_id
    assert _native.inheritance_get(object_id) is value
    assert value.observed_value() == 59, "Python root initialized after the SV child body"
    assert value.count.value == 59 and value.child_value.value == 100
    _check_projected_policy(value, "PYTHON")
    assert value.check(1) == 160 and value.fixed(1) == 360
    value.child_value.value = 200
    assert value.check(1) == 260
    root_field, own_field = value.count, value.child_value
    root_field.value = 61
    assert value.check(1) == 262 and value.observed_value() == 59
    svx.close_instance(object_id)
    assert _native.inheritance_get(object_id) is None
    for retained_field in (root_field, own_field):
        try:
            _ = retained_field.value
        except ExternalStorageError:
            pass
        else:
            raise AssertionError("Python-origin child retained an active projected field")
    assert value.local.value == 7
    before = len(constructed_roots)
    outer = Child(75)
    assert len(constructed_roots) == before + 2
    assert constructed_roots[-2] is outer
    assert outer.observed_value() == 75 and outer.check(1) == 176
    svx.close_instance(outer._svx_remote_object_id)
    print("PYTHON_ROOT_PROXY_PYTHON_CHILD_PASS", flush=True)


@svx.export(name="python_root.create_python_derived")
def create_python_derived():
    global derived_owner, derived_field
    from tests.integration.python_root_derived import Derived

    before = len(constructed_roots)
    derived_owner = Derived(83)
    assert len(constructed_roots) == before + 1 and constructed_roots[-1] is derived_owner
    assert _native.inheritance_get(derived_owner._svx_remote_object_id) is derived_owner
    assert derived_owner.observed_value() == 83
    assert derived_owner.check(1) == 1184
    assert derived_owner.fixed(1) == 384
    derived_field = derived_owner.count
    svx.publish_object("python_root.derived", derived_owner)


@svx.export(name="python_root.check_python_derived_release")
def check_python_derived_release():
    assert _native.inheritance_get(derived_owner._svx_remote_object_id) is None
    try:
        _ = derived_field.value
    except ExternalStorageError:
        pass
    else:
        raise AssertionError("later Python portion retained active root storage")
    assert derived_owner.own_value.value == 1000
    assert derived_owner.local.value == 7
    print("PYTHON_ROOT_PROXY_PYTHON_DERIVED_PASS", flush=True)


sv_derived_owner = None
sv_derived_fields = None


@svx.export(name="python_root.check_sv_derived")
def check_sv_derived():
    global sv_derived_owner, sv_derived_fields
    candidates = [value for value in constructed_roots
                  if getattr(value, "__svx_foreign_class_id__", None) == DERIVED_ID
                  and _native.inheritance_get(value._svx_remote_object_id) is value]
    assert len(candidates) == 1
    sv_derived_owner = candidates[0]
    assert constructed_roots.count(sv_derived_owner) == 1
    assert sv_derived_owner.observed_value() == 87
    assert sv_derived_owner.check(1) == 1188
    assert sv_derived_owner._svx_initialized_python_portions == {ROOT_ID, DERIVED_ID}
    assert sv_derived_owner._svx_pending_python_target_id is None
    sv_derived_fields = (sv_derived_owner.count, sv_derived_owner.child_value, sv_derived_owner.own_value)
    sv_derived_owner.own_value.value = 2000
    sv_derived_owner.child_value.value = 300


@svx.export(name="python_root.check_sv_derived_release")
def check_sv_derived_release():
    assert _native.inheritance_get(sv_derived_owner._svx_remote_object_id) is None
    for field in sv_derived_fields:
        try:
            _ = field.value
        except ExternalStorageError:
            pass
        else:
            raise AssertionError("SV-origin derived portion retained active storage")
    assert sv_derived_owner.local.value == 7
    print("PYTHON_ROOT_PROXY_SV_DERIVED_PASS", flush=True)


grandchild_owner = None
grandchild_fields = None


def verify_grandchild(value, seed):
    assert _native.inheritance_get(value._svx_remote_object_id) is value
    assert value.observed_value() == seed and value.observed_python() == 1000
    assert value.check(1) == seed + 1601 and value.fixed(1) == seed + 701
    assert value._svx_initialized_python_portions == {ROOT_ID, DERIVED_ID}
    assert value._svx_pending_python_portions == ()
    assert constructed_roots.count(value) == 1
    fields = (value.count, value.child_value, value.own_value, value.e_value)
    value.own_value.value = 2000
    value.e_value.value = 600
    assert value.check(1) == seed + 2701
    return fields


@svx.export(name="python_root.check_python_grandchild")
def check_python_grandchild():
    from svx_mirror.python_root_probe_pkg import Grandchild
    value = Grandchild(91)
    fields = verify_grandchild(value, 91)
    svx.close_instance(value._svx_remote_object_id)
    for field in fields:
        try:
            _ = field.value
        except ExternalStorageError:
            pass
        else:
            raise AssertionError("Python-origin E retained active fields")
    print("PYTHON_ROOT_PROXY_PYTHON_E_PASS", flush=True)


@svx.export(name="python_root.check_sv_grandchild")
def check_sv_grandchild():
    global grandchild_owner, grandchild_fields
    candidates = [value for value in constructed_roots
                  if getattr(value, "__svx_foreign_class_id__", None) == "sv://python_root_probe_pkg/Grandchild"
                  and _native.inheritance_get(value._svx_remote_object_id) is value]
    assert len(candidates) == 1
    grandchild_owner = candidates[0]
    grandchild_fields = verify_grandchild(grandchild_owner, 93)


@svx.export(name="python_root.check_sv_grandchild_release")
def check_sv_grandchild_release():
    assert _native.inheritance_get(grandchild_owner._svx_remote_object_id) is None
    for field in grandchild_fields:
        try:
            _ = field.value
        except ExternalStorageError:
            pass
        else:
            raise AssertionError("SV-origin E retained active fields")
    print("PYTHON_ROOT_PROXY_SV_E_PASS", flush=True)


final_owner = None
final_fields = None


@svx.export(name="python_root.create_final")
def create_final():
    global final_owner, final_fields
    from tests.integration.python_root_final import Final

    before = len(constructed_roots)
    final_owner = Final(95)
    assert len(constructed_roots) == before + 1 and constructed_roots[-1] is final_owner
    assert _native.inheritance_get(final_owner._svx_remote_object_id) is final_owner
    assert final_owner.observed_value() == 95 and final_owner.observed_python() == 1000
    assert final_owner.check(1) == 4696
    assert final_owner.fixed(1) == 796
    final_fields = (final_owner.count, final_owner.child_value, final_owner.own_value, final_owner.e_value)
    svx.publish_object("python_root.final", final_owner)


@svx.export(name="python_root.check_final_release")
def check_final_release():
    assert _native.inheritance_get(final_owner._svx_remote_object_id) is None
    for field in final_fields:
        try:
            _ = field.value
        except ExternalStorageError:
            pass
        else:
            raise AssertionError("final Python receiver retained active ancestor fields")
    assert final_owner.f_value.value == 3000
    print("PYTHON_ROOT_PROXY_FINAL_PASS", flush=True)


@svx.export(name="python_root.check_owner")
def check_owner():
    global retained, retained_id
    # This fixture creates exactly one real native-bound root companion.
    for object_id in range(1, 10):
        instance = _native.inheritance_get(object_id)
        if isinstance(instance, Root):
            retained_id = object_id
            assert instance._svx_remote_object_id == object_id
            assert instance.count.value == 41
            assert instance.local.value == 7
            _check_projected_policy(instance, "SV")
            retained = instance.count
            instance.count.value = 42
            local = Root(5)
            assert local.count.value == 5
            assert instance.count.value == 42
            return
    raise AssertionError("SV root constructor did not bind its Python companion")


def _check_projected_policy(instance, origin):
    original = instance.count.value
    root_count = len(constructed_roots)
    own_field = getattr(instance, "child_value", None)
    if own_field is not None:
        own_field.rand_mode(0)
    instance.mode.rand_mode(0)
    instance.local.rand_mode(0)
    instance.cycle.rand_mode(0)
    try:
        def selected(item):
            item.count == 52

        assert instance.randomize_with(selected)
        assert instance.count.value == 52
        assert instance.check(0) == (152 if origin == "PYTHON" else 52)
        assert instance.local.value == 7
        assert instance.randomize()
        assert 0 <= instance.count.value <= 127
        before_failure = instance.count.value

        def impossible(item):
            item.count == -1

        assert not instance.randomize_with(impossible)
        assert instance.count.value == before_failure
        assert len(constructed_roots) == root_count
        instance.svtypes_auto_cov.sample()
        coverage = instance.svtypes_auto_cov.instance.snapshot()['count']
        assert coverage['samples'] == 1
        assert sum(coverage['hits'].values()) == 1
        print(f"PYTHON_ROOT_PROJECTED_POLICY_{origin}_PASS", flush=True)
    finally:
        instance.count.value = original
        instance.local.rand_mode(1)
        instance.mode.rand_mode(1)
        instance.cycle.rand_mode(1)
        if own_field is not None:
            own_field.rand_mode(1)
    _check_projected_randc(instance, origin)
    _check_projected_hooks(instance, origin)


def _check_projected_randc(instance, origin):
    from svtypes import RandomContext

    root_count = len(constructed_roots)
    original = instance.cycle.value
    fields = [getattr(instance, name, None) for name in ('count', 'local', 'mode', 'child_value')]
    modes = [(field, field.rand_mode()) for field in fields if field is not None]
    for field, _ in modes:
        field.rand_mode(0)
    try:
        with RandomContext(seed=401):
            values = []
            for _ in range(2):
                assert instance.randomize()
                values.append(instance.cycle.value)
            instance.cycle.rand_mode(0)
            assert instance.randomize()
            assert instance.cycle.value == values[-1]
            instance.cycle.rand_mode(1)

            def impossible(item):
                item.count == -1

            assert instance.randomize_with(impossible) is False
            assert instance.cycle.value == values[-1]
            for _ in range(2):
                assert instance.randomize()
                values.append(instance.cycle.value)
        assert set(values) == {0, 1, 2, 3}
        assert len(constructed_roots) == root_count
        print(f"PYTHON_ROOT_PROJECTED_RANDC_{origin}_PASS", flush=True)
    finally:
        instance.cycle.value = original
        instance.cycle.rand_mode(1)
        for field, mode in modes:
            field.rand_mode(mode)


def _check_projected_hooks(instance, origin):
    root_count = len(constructed_roots)
    original = instance.count.value
    fields = [getattr(instance, name, None) for name in ('count', 'cycle', 'local', 'mode', 'child_value')]
    modes = [(field, field.rand_mode()) for field in fields if field is not None]
    values = [(field, field.value) for field, _ in modes]
    for field, _ in modes:
        field.rand_mode(0)
    instance.count.rand_mode(1)
    instance._test_random_hooks = True
    instance._test_hook_events = []
    try:
        def selected(item):
            item.count == 52

        assert instance.randomize_with(selected)
        assert instance._test_hook_events == [('pre', False, 0, original), ('post', False, 0, 52)]
        instance._test_hook_events.clear()

        def impossible(item):
            item.count == -1

        assert instance.randomize_with(impossible) is False
        assert instance._test_hook_events == [('pre', False, 0, 52)]
        instance._test_hook_events.clear()
        instance.cycle.rand_mode(1)
        assert instance.layered_randomize()
        assert [(kind, active, priority) for kind, active, priority, _ in instance._test_hook_events] == [
            ('pre', True, 5), ('post', True, 5), ('pre', True, 0), ('post', True, 0),
        ]
        assert instance.svtypes_layered_randomize_active() is False
        assert instance.svtypes_layered_randomize_priority() == 0
        assert len(constructed_roots) == root_count
        print(f"PYTHON_ROOT_PROJECTED_HOOKS_{origin}_PASS", flush=True)
    finally:
        instance._test_random_hooks = False
        for field, value in values:
            field.value = value
        for field, mode in modes:
            field.rand_mode(mode)


@svx.export(name="python_root.check_release")
def check_release():
    assert _native.inheritance_get(retained_id) is None
    try:
        _ = retained.value
    except ExternalStorageError:
        pass
    else:
        raise AssertionError("retained root field remained valid after release")
    print("PYTHON_ROOT_PROXY_OWNER_PASS", flush=True)


@svx.export(name="python_root.check_failed_initializer")
def check_failed_initializer():
    global failed_owner
    payload = encode_constructor(ROOT_ID, {"seed": 99})
    try:
        create_python_instance(ROOT_ID, 77, payload)
    except ValueError as error:
        assert str(error) == "root initializer failure after SV write"
    else:
        raise AssertionError("generated root companion lost the initializer exception")
    assert _native.inheritance_get(77) is None
    assert failed_owner.local.value == 7
    try:
        _ = failed_owner.count.value
    except ExternalStorageError:
        pass
    else:
        raise AssertionError("failed initializer left its projected storage active")
    failed_owner = None
    print("PYTHON_ROOT_PROXY_INIT_FAILURE_PASS", flush=True)


@svx.export(name="python_root.check_shared_module")
def check_shared_module():
    import inspect
    import sys
    from svx_py.tests.integration.python_root_proxy_test import Root as PairedRoot, PlainRoot as PairedPlain
    from svx_py.tests.integration.python_root_derived import Derived as PairedDerived
    from svx_mirror.python_root_probe_pkg import Child, Grandchild
    from tests.integration.python_root_derived import Derived
    from tests.integration.python_root_final import Final

    assert PairedRoot.__name__ == "Root" and PairedPlain.__name__ == "PlainRoot"
    assert PairedRoot.__module__ == PairedPlain.__module__ == "svx_py.tests.integration.python_root_proxy_test"
    assert PairedDerived.__module__ == "svx_py.tests.integration.python_root_derived"
    assert Child.__bases__[0] is PairedRoot and Grandchild.__bases__[0] is PairedDerived
    assert inspect.signature(PairedRoot) == inspect.signature(Root)
    assert inspect.signature(PairedPlain) == inspect.signature(PlainRoot)
    assert Child.__module__ == Grandchild.__module__ == "svx_mirror.python_root_probe_pkg"
    assert Child.__qualname__ == "Child" and Grandchild.__qualname__ == "Grandchild"
    assert tuple(inspect.signature(Child).parameters) == ("child_seed",)
    assert tuple(inspect.signature(Grandchild).parameters) == ("e_seed",)
    assert issubclass(Derived, Child) and issubclass(Final, Grandchild)
    assert "python_root_child_mirror" not in sys.modules
    assert "python_root_grandchild_mirror" not in sys.modules
    assert "python_root_companion" not in sys.modules
    assert "python_root_derived_companion" not in sys.modules
    print("PYTHON_ROOT_PROXY_MODULE_PASS", flush=True)
