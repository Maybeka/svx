"""A new Python-only case: no new SV class, method slot or generated contract."""
from uart_migration import PythonUart


class Test(PythonUart):
    def tx_pattern(self):
        return tuple(range(256))

    def rx_pattern(self):
        return tuple(range(255, -1, -1))
