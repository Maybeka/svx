import svx
import svx.inheritance as inheritance
from svtypes import ExternalStorageError
from svx import _native
from svx_mirror.same_package_pkg import A, C
from tests.integration.same_package_test import B, constructed

seen = []
verified = 0
original_check = A.check


def check(self):
    if not any(value is self for value, _ in seen):
        seen.append((self, self.count.value))
    return original_check(self)


A.check = check


def stale(field):
    try:
        _ = field.value
    except ExternalStorageError:
        return
    raise AssertionError('nested projected field remained live after release')


def verify_pair(kind, value=None):
    global verified
    assert len(seen) == verified + 2
    (inner, inner_early), (outer, outer_early) = seen[-2:]
    assert inner is not outer and inner_early == outer_early == 11
    assert type(inner) is A
    assert _native.inheritance_get(inner._svx_remote_object_id) is None
    stale(inner.count)
    assert value is None or outer is value
    assert _native.inheritance_get(outer._svx_remote_object_id) is outer
    if kind == 'a':
        assert type(outer) is A and outer.check() == 11
        outer.count.value = 19
        assert outer.check() == 19
        fields = (outer.count,)
    else:
        assert constructed.count(outer) == 1
        assert outer.check() == (35 if kind == 'b' else 135)
        assert outer.local.value == 7
        fields = (outer.count,) if kind == 'b' else (outer.count, outer.retry, outer.extra)
        if kind == 'c':
            assert type(outer) is C and outer.observed_value() == 23
    svx.close_instance(outer)
    for field in fields:
        stale(field)
    if kind == 'b':
        assert outer.retry.value == 23 and outer.local.value == 7
    verified += 2


@svx.export(name='nested_literal.create_a')
def create_a():
    verify_pair('a', A())
    svx.display('NESTED_LITERAL_PYTHON_A_PASS')


@svx.export(name='nested_literal.create_b')
def create_b():
    verify_pair('b', B())
    svx.display('NESTED_LITERAL_PYTHON_B_PASS')


@svx.export(name='nested_literal.verify_sv_a')
def verify_sv_a():
    verify_pair('a')
    svx.display('NESTED_LITERAL_SV_A_PASS')


@svx.export(name='nested_literal.verify_sv_c')
def verify_sv_c():
    verify_pair('c')
    svx.display('NESTED_LITERAL_SV_C_PASS')


@svx.export(name='nested_literal.verify_all_closed')
def verify_all_closed():
    assert len(seen) == verified == 8
    assert len({value._svx_remote_object_id for value, _ in seen}) == 8
    for value, _ in seen:
        assert _native.inheritance_get(value._svx_remote_object_id) is None
        stale(value.count)
    assert not inheritance._reserved_python_receivers
    svx.display('NESTED_LITERAL_ALL_CLOSED_PASS')
