"""Python-only extension added after the initial native/SV build."""
from uart_migration import PythonUart


class Test(PythonUart):
    def tx_pattern(self):
        return tuple((index * 73 + 19) & 255 for index in range(256))

    def rx_pattern(self):
        return tuple((index * 29 + 7) & 255 for index in range(256))
