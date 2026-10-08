from svtypes import Int, SvObject, svobj

events = []
mismatch_super = False
check_declared_default = False
fail_root = False
fail_derived = False


@svobj
class Root(SvObject):
    count = Int(17)
    local = Int()

    def __init__(self, seed):
        super().__init__()
        if check_declared_default:
            assert self.count.value == 17, 'SV storage lost packed declaration initializer'
        self.count.value = seed
        self.local.value = 7
        events.append(('root', seed, self))
        if fail_root:
            raise ValueError('Python-root Root initializer failed')

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


from svx_mirror.hetero_child_pkg import Child


class Derived(Child, Root):
    own_value = Int()

    def __init__(self, child_seed, label):
        super().__init__(child_seed + (1 if mismatch_super else 0), label)
        assert self.observed_value() == child_seed + (1 if mismatch_super else 0) + 10
        self.own_value.value = 1000 + len(label)
        events.append(('derived', child_seed, label, self))
        if fail_derived:
            raise ValueError('Python-root Derived initializer failed')

    def check(self, delta):
        return super().check(delta) + self.own_value.value
