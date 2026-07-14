`ifndef SVX_SIGNAL__SV
`define SVX_SIGNAL__SV

import "DPI-C" context function int svx_vpi_signal_validate(string path, int width);
import "DPI-C" context function int svx_vpi_signal_write(
  string path, int width, chandle data, int size, int operation
);
import "DPI-C" context function int svx_vpi_signal_read(
  string path, int width, chandle data, int size
);

task automatic svx_signal_validate(string path, int width, output int result);
  result = svx_vpi_signal_validate(path, width);
endtask

task automatic svx_signal_apply(
  string path, int width, chandle data, int size, int operation, output bit ok
);
  ok = svx_vpi_signal_write(path, width, data, size, operation);
endtask

task automatic svx_signal_read(
  string path, int width, chandle data, int size, output bit ok
);
  ok = svx_vpi_signal_read(path, width, data, size) == 1;
endtask

export "DPI-C" task svx_signal_validate;
export "DPI-C" task svx_signal_apply;
export "DPI-C" task svx_signal_read;

`endif
