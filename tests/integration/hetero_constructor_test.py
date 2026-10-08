import svx
from svx_mirror.hetero_final_pkg import Grandchild
from tests.integration.hetero_constructor_source import Derived, events

objects = []


@svx.export(name='hetero_constructor.fail')
def fail():
    from svx import inheritance, _native
    from svtypes import ExternalStorageError
    from tests.integration import hetero_constructor_source as source
    original = svx.SVMirror._svx_retire_failed_python_companion
    checked = set()

    def verify_retirement(instance, error):
        original(instance, error)
        if id(instance) in checked or inheritance._natural_constructor_segments.pending_count:
            return
        object_id = instance._svx_remote_object_id
        assert _native.inheritance_get(object_id) is None
        assert object_id not in inheritance._reserved_python_receivers
        for name in instance.__svx_root_field_ids__:
            try:
                _ = getattr(instance, name).value
            except ExternalStorageError:
                pass
            else:
                raise AssertionError('failed constructor retained projected storage')
        checked.add(id(instance))
        print('HETERO_CONSTRUCTOR_ROLLBACK_PYTHON_PASS', flush=True)

    svx.SVMirror._svx_retire_failed_python_companion = verify_retirement
    source.fail_derived = True


@svx.export(name='hetero_constructor.fail_root')
def fail_root():
    fail()
    from tests.integration import hetero_constructor_source as source
    source.fail_root = True
    source.fail_derived = False


@svx.export(name='hetero_constructor.fail_create')
def fail_create():
    Grandchild()
    raise AssertionError('failing constructor unexpectedly returned')


@svx.export(name='hetero_constructor.defaults')
def defaults():
    from tests.integration import hetero_constructor_source
    hetero_constructor_source.check_declared_default = True


@svx.export(name='hetero_constructor.transformed')
def transformed():
    from tests.integration import hetero_constructor_source
    hetero_constructor_source.mismatch_super = True
    try:
        value = Grandchild()
    finally:
        hetero_constructor_source.mismatch_super = False
    assert [(event[0], event[1]) for event in events] == [('root', 18), ('derived', 7)]
    assert events[0][-1] is value and events[-1][-1] is value
    assert value.count.value == 18 and value.own_value.value == 1003
    assert value.check(1) == 1622 and value.observed_value() == 18
    from svx import inheritance
    assert inheritance._natural_constructor_segments.pending_count == 0
    assert value._svx_pending_python_portions == ()
    svx.close_instance(value)
    events.clear()
    print('HETERO_CONSTRUCTOR_TRANSFORMED_SUPER_PASS', flush=True)


@svx.export(name='hetero_constructor.verify_sv')
def verify_sv():
    assert [(event[0], event[1]) for event in events] == [('root', 17), ('derived', 7)]
    final = events[-1][-1]
    assert events[0][-1] is final
    assert final.count.value == 17 and final.own_value.value == 1003
    assert final.check(1) == 1621 and final.observed_python() == 1003
    svx.close_instance(final)
    events.clear()
    print('HETERO_CONSTRUCTOR_SV_PASS', flush=True)


@svx.export(name='hetero_constructor.create')
def create():
    derived = Derived(23, 'hello')
    assert [(event[0], event[1]) for event in events] == [('root', 33), ('derived', 23)]
    assert events[-1][2] == 'hello' and events[0][-1] is derived
    assert derived.check(1) == 1139
    assert derived.local.value == 7 and derived.own_value.value == 1005
    events.clear()
    from tests.integration import hetero_constructor_source
    hetero_constructor_source.mismatch_super = True
    try:
        transformed = Derived(23, 'hello')
    finally:
        hetero_constructor_source.mismatch_super = False
    assert [(event[0], event[1]) for event in events] == [('root', 34), ('derived', 23)]
    assert transformed.count.value == 34 and transformed.check(1) == 1140
    assert events[0][-1] is transformed
    events.clear()
    final = Grandchild()
    assert [(event[0], event[1]) for event in events] == [('root', 17), ('derived', 7)]
    assert events[0][-1] is final and events[-1][-1] is final
    assert final.check(1) == 1621
    objects.extend([derived, transformed, final])
    svx.publish_object('hetero.derived', derived)
    svx.publish_object('hetero.final', final)
    print('HETERO_CONSTRUCTOR_PYTHON_PASS', flush=True)


@svx.export(name='hetero_constructor.close')
def close():
    for instance in objects:
        svx.close_instance(instance)
    objects.clear()
    events.clear()
    print('HETERO_CONSTRUCTOR_CLOSE_PASS', flush=True)
