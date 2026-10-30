"""Default-base UVMX startup without generated test or base registrations."""

import svx
from uvmx import Test, uvm_test


@uvm_test(
    canonical_id="py://verification/SmokeTest",
    factory_name="python_smoke",
)
class SmokeTest(Test):
    def run_phase(self):
        svx.display("UVMX_MINIMAL_START")
        svx.delay(2, "ns")
        svx.display("UVMX_MINIMAL_PASS")
