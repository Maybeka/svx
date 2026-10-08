from svtypes import Int, SvObject, svobj

constructed_roots = []
constructed_derived = []
mismatch_super = False


@svobj
class Root(SvObject):
    count = Int()
    local = Int()

    def __init__(self, seed):
        super().__init__()
        assert self.count.value == 0
        self.count.value = seed
        self.local.value = 7
        constructed_roots.append(self)

    def check(self, delta):
        return self.count.value + delta

    def fixed(self, delta):
        return self.count.value + delta + 200

    @staticmethod
    def scale(delta):
        return delta * 3

    @staticmethod
    def wait_once():
        import svx
        svx.delay(1, 'ns')


from svx_mirror.python_unit_pkg import Child


class Derived(Child, Root):
    own_value = Int()

    def __init__(self, child_seed):
        super().__init__(child_seed + (1 if mismatch_super else 0))
        assert self.observed_value() == child_seed and self.own_value.value == 0
        self.own_value.value = 1000
        constructed_derived.append(self)

    def check(self, delta):
        return super().check(delta) + self.own_value.value
