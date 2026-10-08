"""Python declarations used by the UVMX U0 peer-selection regression."""

import svx
from svtypes import Bit, Int, SvObject, svobj
from uvmx import Test, uvm_test


@svobj
class BootstrapTransaction(SvObject):
    address = Bit[16]()
    data = Int()


@uvm_test(
    canonical_id="py://svx/incubator/uvmx/PySmokeTest",
    sv_base="uvmx_peer_pkg::uvmx_python_base",
    factory_name="py_smoke_test",
)
class PySmokeTest(Test):
    def build_phase(self) -> None:
        svx.display("UVMX Python build_phase")

    def run_phase(self) -> None:
        transaction = BootstrapTransaction()
        transaction.address.value = 0x41
        transaction.data.value = 73
        svx.channel("uvmx.peer.transaction").put(transaction)
        svx.delay(2, "ns")
        svx.display("UVMX Python run_phase complete")


@uvm_test(
    canonical_id="py://svx/incubator/uvmx/PyBlockingBuildTest",
    sv_base="uvmx_peer_pkg::uvmx_python_base",
    factory_name="py_blocking_build_test",
)
class PyBlockingBuildTest(Test):
    def build_phase(self) -> None:
        # The regression expects the U0 function-phase guard to reject this
        # before any simulation time can advance.
        svx.delay(1, "ns")


@uvm_test(
    canonical_id="py://svx/incubator/uvmx/PyExceptionTest",
    sv_base="uvmx_peer_pkg::uvmx_python_base",
    factory_name="py_exception_test",
)
class PyExceptionTest(Test):
    def build_phase(self) -> None:
        raise RuntimeError("UVMX Python callback failure")
