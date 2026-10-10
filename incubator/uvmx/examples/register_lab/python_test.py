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
