`ifndef SVX_INIT__SV
`define SVX_INIT__SV

localparam int unsigned SVX_SV_RUNTIME_ABI_VERSION = 1;
localparam string SVX_SV_PRODUCT_VERSION = "1.0.0";

import "DPI-C" context task svx_runtime_init(
  int unsigned sv_runtime_abi_version,
  string sv_product_version
);
import "DPI-C" context task svx_runtime_init_with_signal_declarations(
  int unsigned sv_runtime_abi_version,
  string sv_product_version,
  string module_name
);
import "DPI-C" context task svx_runtime_load(string module_name);
import "DPI-C" context task svx_runtime_start(string export_name);
import "DPI-C" context task svx_runtime_shutdown();
import "DPI-C" context function int unsigned svx_runtime_abi_version();
import "DPI-C" context function string svx_runtime_state_name();

task automatic svx_init();
  svx_runtime_init(SVX_SV_RUNTIME_ABI_VERSION, SVX_SV_PRODUCT_VERSION);
endtask

task automatic svx_init_with_signal_declarations(string module_name);
  svx_runtime_init_with_signal_declarations(
    SVX_SV_RUNTIME_ABI_VERSION,
    SVX_SV_PRODUCT_VERSION,
    module_name
  );
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
