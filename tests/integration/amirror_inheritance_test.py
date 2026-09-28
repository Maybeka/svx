import svx

from svx_mirror.amirror_pkg import Base


class PythonChild(Base):
    def ping(self):
        svx.display("AMIRROR_PYTHON_OVERRIDE")
        svx.delay(2, "ns")
