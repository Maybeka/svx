import svx
from svx_mirror.parameterized_pkg import Base


class Derived(Base):
    def check(self, value):
        return super().check(value) + 100

    def observe(self, result):
        assert super().observe(result) is None
        result.value += 100

    def collisions(self, ok, request, response, error, bytes, offset,
                   request_value, response_value, svx_ok, result):
        returned = super().collisions(ok, request, response, error, bytes, offset,
                                      request_value, response_value, svx_ok, result)
        result.value += 100
        return returned + 200


@svx.export(name="parameterized_mirror.run")
def run():
    value = Derived()
    assert value.count.value == 7
    assert value.get_count() == 7
    value.count.value = 19
    assert value.get_count() == 19
    assert value.call_check(3) == 129, "closed specialization lost Python override or SV super"
    assert value.call_observe() == 119, "void function callback lost output named result"
    observed = svx.Output()
    assert value.observe(observed) is None
    assert observed.value == 119, "Python super lost the output formal named result"
    assert value.call_collisions() == 391, "generated bridge locals collided with user formals"
    observed = svx.Output()
    assert value.collisions(1, 2, 3, 4, 5, 6, 7, 8, 9, observed) == 246
    assert observed.value == 145, "return and output result were confused"
    value.set_count(23)
    assert value.count.value == 23
    svx.close_instance(value._svx_remote_object_id)
    svx.display("SVX_PARAMETERIZED_MIRROR_PASS")
