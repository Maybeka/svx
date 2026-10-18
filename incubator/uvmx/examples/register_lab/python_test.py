"""Optional UVM factory launch of the core register lab, with unchanged timing."""

import svx
from uvmx import Test, uvm_test


@uvm_test(canonical_id="py://svx/incubator/uvmx/register_lab/PythonTest",
          factory_name="register_lab_python_test")
class PythonTest(Test):
    def run_phase(self):
        from examples.register_lab.scenarios import smoke

        smoke()
        svx.display("REGISTER_LAB_UVMX_PASS")


@uvm_test(canonical_id="py://svx/incubator/uvmx/register_lab/PythonExtendedTest",
          factory_name="register_lab_extended_test")
class PythonExtendedTest(PythonTest):
    def __init__(self):
        self.completed_runs = 0

    def build_phase(self):
        assert self.completed_runs == 0
        svx.display("REGISTER_LAB_UVMX_EXTENDED_BUILD_PASS")

    def run_phase(self):
        super().run_phase()
        self.completed_runs += 1
        assert self.completed_runs == 1
        svx.display("REGISTER_LAB_UVMX_EXTENDED_PASS")
