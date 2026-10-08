import svx
from svx import _native
from svtypes import Int, ExternalStorageError
from svx_mirror.sv_root_pkg import A
from svx_mirror.sv_root_child_pkg import C
from tests.integration.sv_root_target_test import B, constructed

second = []
python_values = []


class B2(A):
    retry = Int()
    local = Int()

    def __init__(self):
        super().__init__()
        assert self.count.value == 11
        self.count.value = 22
        self.retry.value = 40
        self.local.value = 8
        second.append(self)

    def check(self):
        return super().check() + self.retry.value


def verify(value, branch):
    expected = 135 if branch == 1 else 262
    owners = constructed if branch == 1 else second
    source = B if branch == 1 else B2
    assert isinstance(value, source) and owners.count(value) == 1
    assert _native.inheritance_get(value._svx_remote_object_id) is value
    assert value.check() == expected
    assert value.observed_value() == (23 if branch == 1 else 40)
    assert value.local.value == (7 if branch == 1 else 8)
    if hasattr(A, 'prefix_count'):
        assert value.prefix_count.value == value.prefix_value() == 400
        assert value.prefix_virtual() == (423 if branch == 1 else 400)
        assert value.prefix_scale() == 800


@svx.export(name='sv_root_branches.create')
def create():
    from svx_mirror.sv_root_branch_pkg import C2
    for branch, cls in ((1, C), (2, C2)):
        value = cls()
        verify(value, branch)
        python_values.append(value)
        svx.publish_object('sv_root_branches.c' + str(branch), value)
    assert python_values[0]._svx_remote_object_id != python_values[1]._svx_remote_object_id
    svx.display('SV_ROOT_BRANCHES_PYTHON_PASS')


@svx.export(name='sv_root_branches.close')
def close():
    for branch, value in enumerate(python_values, 1):
        verify(value, branch)
        fields = value.count, value.retry, value.extra
        if hasattr(A, 'prefix_count'):
            fields += (value.prefix_count,)
        svx.close_instance(value)
        for field in fields:
            try:
                _ = field.value
            except ExternalStorageError:
                pass
            else:
                raise AssertionError('branch retained live projected field')
        assert value.local.value == (7 if branch == 1 else 8)
    svx.display('SV_ROOT_BRANCHES_CLOSE_PASS')


@svx.export(name='sv_root_branches.verify_sv')
def verify_sv():
    for branch, owners in ((1, constructed), (2, second)):
        live = [value for value in owners if _native.inheritance_get(value._svx_remote_object_id) is value]
        assert len(live) == 1
        verify(live[0], branch)
        svx.close_instance(live[0])
    svx.display('SV_ROOT_BRANCHES_SV_PASS')
