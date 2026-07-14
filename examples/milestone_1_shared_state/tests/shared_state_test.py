import svx


class SharedCounter:
    def __init__(self):
        self.value = 0
        self.history = []

    def writer(self):
        svx.display(f"writer initial value={self.value}")
        svx.delay(1.0, "ns")
        self.value = 7
        self.history.append(("writer", self.value))
        svx.display(f"writer updated value={self.value}")

    def reader(self):
        svx.display(f"reader initial value={self.value}")
        svx.delay(2.0, "ns")
        self.history.append(("reader", self.value))
        svx.display(f"reader observed value={self.value}")
        if self.value != 7:
            raise AssertionError(f"expected shared value 7, got {self.value}")


counter = SharedCounter()


@svx.export
def main():
    svx.display("shared-state test start")
    svx.fork_join([counter.writer, counter.reader])
    svx.display(f"shared-state final value={counter.value}")
    svx.display(f"shared-state history={counter.history}")
    if counter.history != [("writer", 7), ("reader", 7)]:
        raise AssertionError(f"unexpected history: {counter.history!r}")
    svx.display("shared-state test done")
