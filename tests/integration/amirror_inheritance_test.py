import svx

from svx_mirrors.amirror_pkg import BaseMirror


class PythonChild(BaseMirror):
    def ping(self):
        svx.display("AMIRROR_PYTHON_OVERRIDE")
        svx.delay(2, "ns")
