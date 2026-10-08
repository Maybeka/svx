import svx
from tests.integration.amirror_inheritance_test import PythonChild


def prohibited_initializer(self):
    svx.delay(1, "ns")
    raise AssertionError("SV constructor accepted a blocking Python initializer")


PythonChild.__init__ = prohibited_initializer
