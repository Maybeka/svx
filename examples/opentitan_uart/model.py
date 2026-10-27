"""Byte-stream model independent of SV scoreboard prediction state."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Frame:
    data: int
    start: int
    stop: int
    parity: int
    parity_enabled: bool
    odd_parity: bool


class UartModel:
    def __init__(self):
        self.expected = {"TX": [], "RX": []}
        self.readbacks = []

    def sent(self, direction, value):
        self.expected[direction].append(int(value) & 255)

    def read(self, expected, actual):
        assert actual == expected, f"UART_MODEL_READ expected={expected:#x} actual={actual:#x}"
        self.readbacks.append(actual)

    def check(self, observations):
        for direction, frames in observations.items():
            actual = [frame.data for frame in frames]
            expected_stream = self.expected[direction]
            if actual != expected_stream:
                index = next((i for i, (a, b) in enumerate(zip(actual, expected_stream)) if a != b),
                             min(len(actual), len(expected_stream)))
                expected = expected_stream[index] if index < len(expected_stream) else "<end>"
                observed = actual[index] if index < len(actual) else "<end>"
                raise AssertionError(
                    f"UART_MODEL_STREAM {direction} index={index} expected={expected} actual={observed} "
                    f"expected_count={len(expected_stream)} actual_count={len(actual)}")
            for index, frame in enumerate(frames):
                assert (frame.start, frame.stop) == (0, 1), f"UART_MODEL_FRAME {direction} index={index}"
                if frame.parity_enabled:
                    expected = (frame.data.bit_count() & 1) ^ int(frame.odd_parity)
                    assert frame.parity == expected, f"UART_MODEL_PARITY {direction} index={index}"
        assert self.expected["TX"] and self.expected["RX"], "UART_MODEL_EMPTY"
