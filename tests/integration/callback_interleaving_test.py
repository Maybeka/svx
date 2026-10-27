from contextvars import ContextVar
import svx
from svx_mirror.callback_interleaving_pkg import Base

current = ContextVar("callback_interleaving_current", default=0)
events = []
instance = None


class Derived(Base):
    def work(self, tag):
        token = current.set(int(tag))
        events.append(("start", int(tag)))
        try:
            super().work(tag)
            assert current.get() == int(tag), "interleaved callback context leaked"
            events.append(("end", int(tag)))
        finally:
            current.reset(token)

    def check(self, tag):
        assert current.get() == int(tag), "nested callback inherited an unrelated process context"
        events.append(("nested", int(tag)))
        return int(tag) + 10


@svx.export(name="callback_interleaving.create")
def create():
    global instance
    instance = Derived()
    svx.publish_object("callback_interleaving.item", instance)


@svx.export(name="callback_interleaving.verify")
def verify():
    assert events == [("start", 1), ("start", 2), ("nested", 1), ("end", 1),
                      ("nested", 2), ("end", 2)], events
    assert current.get() == 0
    svx.close_instance(instance)
    svx.display("CALLBACK_INTERLEAVING_PYTHON_PASS")
