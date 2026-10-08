from svtypes import Int
from svx_mirror.multi_a_pkg import A

constructed_b = []
constructed_d = []


class B(A):
    retry = Int()
    local = Int()

    def __init__(self):
        super().__init__()
        self.count.value = 12
        self.retry.value = 23
        self.local.value = 7
        constructed_b.append(self)

    def check(self):
        return super().check() + self.retry.value


from svx_mirror.multi_c_pkg import C


class D(C, B):
    own = Int()

    def __init__(self):
        super().__init__()
        self.own.value = 900
        constructed_d.append(self)

    def check(self):
        return super().check() + self.own.value
