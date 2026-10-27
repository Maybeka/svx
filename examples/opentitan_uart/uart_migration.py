"""Python-owned scenarios, expectations and checks over native UART services."""
import os
import importlib
import svx
from svx_mirror.uart_svx_bridge_pkg import UartSequence
from model import Frame, UartModel

sequence = None


def signed_byte(value):
    return value if value < 128 else value - 256


class PythonUart(UartSequence):
    def __init__(self):
        super().__init__()
        self.model = UartModel()
        self.mode = os.environ.get("UART_MIGRATION_MODE", "mixed")
        self.rounds = 0

    def body(self):
        if self.mode == "mixed":
            super().body()
        else:
            for _ in range(2):
                self.uart_init()
                svx.fork_join([self.process_tx, self.process_rx])
                self.dut_shutdown()

    def send_tx_byte(self, data):
        self.model.sent("TX", data)
        super().send_tx_byte(data)

    def send_rx_byte(self, data):
        self.model.sent("RX", data)
        super().send_rx_byte(data)

    def process_tx(self):
        if self.mode == "mixed":
            # SV still owns TX scenario generation; virtual calls record intent in Python.
            super().process_tx()
            return
        for value in self.tx_pattern():
            self.send_tx_byte(signed_byte(value))
            svx.delay(1, "us")
            self.spinwait_txidle()

    def process_rx(self):
        # In mixed mode only RX moves to Python; original SV TX remains concurrent.
        values = (0, 255, 85, 170, 127) if self.mode == "mixed" else self.rx_pattern()
        for value in values:
            self.send_rx_byte(signed_byte(value))
            self.spinwait_rxidle()
            result = svx.Output()
            self.read_rx(result)
            self.model.read(value, int(result.value))
        self.rounds += 1

    def tx_pattern(self):
        return (0, 255, 85, 170, *range(28))

    def rx_pattern(self):
        return tuple(range(31, -1, -1))

    def observations(self):
        result = {}
        for direction, tx in (("TX", 1), ("RX", 0)):
            frames = []
            for index in range(int(self.observed_count(tx))):
                item = self.observed_item(tx, index)
                again = self.observed_item(tx, index)
                assert self.same_item(item, again), "native item identity lost"
                assert self.item_identity(item) == self.item_identity(again)
                flags = int(self.item_frame(item))
                frames.append(Frame(int(self.item_data(item)), flags & 1, (flags >> 1) & 1,
                                    (flags >> 2) & 1, bool(self.parity_enabled(tx, index)),
                                    bool(self.parity_odd(tx, index))))
            result[direction] = frames
        return result


@svx.export(name="uart_migration.create")
def create():
    global sequence
    extension = os.environ.get("UART_MIGRATION_CASE_MODULE")
    test_type = importlib.import_module(extension).Test if extension else PythonUart
    if not isinstance(test_type, type) or not issubclass(test_type, PythonUart):
        raise TypeError("UART_MIGRATION_CASE_MODULE.Test must derive from PythonUart")
    sequence = test_type()
    item = sequence.make_item(0x35)
    assert sequence.item_data(item) == 0x35
    identity = sequence.item_identity(item)
    sequence.set_item_data(item, 0xa6)
    assert sequence.item_data(item) == 0xa6 and sequence.item_identity(item) == identity
    svx.publish_object("uart_migration.sequence", sequence)


@svx.export(name="uart_migration.check")
def check():
    observations = sequence.observations()
    sequence.model.check(observations)
    assert sequence.rounds == 2
    tx_count = 10 if sequence.mode == "mixed" else len(sequence.tx_pattern()) * 2
    rx_count = 10 if sequence.mode == "mixed" else len(sequence.rx_pattern()) * 2
    assert len(sequence.model.expected["TX"]) == tx_count
    assert len(sequence.model.expected["RX"]) == rx_count
    assert len(sequence.model.readbacks) == rx_count
    enabled = sum(frame.parity_enabled for frames in observations.values() for frame in frames)
    odd = sum(frame.parity_enabled and frame.odd_parity for frames in observations.values() for frame in frames)
    svx.display(f"UART_MODEL_PARITY_CONFIG enabled_frames={enabled} odd_frames={odd}")
    svx.display(f"UART_MIGRATION_PASS mode={sequence.mode} tx={tx_count} rx={rx_count} readbacks={rx_count}")
    svx.close_instance(sequence)
