"""Import this module only after compiling the peer-selection baseline."""

import svx
from uvmx import uvm_test
from python_tests import PySmokeTest


@uvm_test(canonical_id='py://uvmx/dynamic/ImportedAfterCompile',
          sv_base='uvmx_peer_pkg::uvmx_python_base',
          factory_name='py_imported_after_compile')
class ImportedAfterCompile(PySmokeTest):
    def __init__(self):
        self.python_only_state = 51

    def connect_phase(self):
        assert self.python_only_state == 51
        svx.display('UVMX_IMPORTED_CONNECT_PASS')

    def run_phase(self):
        super().run_phase()
        self.python_only_state += 1
        assert self.python_only_state == 52
        svx.delay(1, 'ns')
        svx.display('UVMX_IMPORTED_RUN_PASS')
