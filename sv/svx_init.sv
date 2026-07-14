`ifndef SVX_INIT__SV
`define SVX_INIT__SV

import "DPI-C" context task svx_runtime_init();
import "DPI-C" context task svx_runtime_init_with_signal_declarations(string module_name);
import "DPI-C" context task svx_runtime_load(string module_name);
import "DPI-C" context task svx_runtime_start(string export_name);

task automatic svx_init();
  svx_runtime_init();
endtask

task automatic svx_init_with_signal_declarations(string module_name);
  svx_runtime_init_with_signal_declarations(module_name);
endtask

task automatic svx_load(string module_name);
  svx_runtime_load(module_name);
endtask

task automatic svx_start(string export_name);
  svx_runtime_start(export_name);
endtask

task automatic svx_run_test(string module_name, string function_name);
  svx_load(module_name);
  svx_start({module_name, ".", function_name});
endtask

`endif
