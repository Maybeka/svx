import svx
from svx_mirror.iteration_pkg import Driver


class Derived(Driver):
    def check(self, svx_return_value):
        return super().check(svx_return_value) + 100


@svx.export(name="iteration_body.run")
def run():
    value = Derived(1, 2, 3, 4, 5, 6)
    assert value.call_check(3) == 125
    svx.close_instance(value._svx_remote_object_id)
    svx.display("SVX_ITERATION_SECOND_PASS")
