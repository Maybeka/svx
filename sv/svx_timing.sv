`ifndef SVX_TIMING__SV
`define SVX_TIMING__SV

task automatic delay_svx(real duration, int unit_code);
  case (e_svx_time_unit'(unit_code))
    SVX_TIME_S : #(duration * 1s);
    SVX_TIME_MS: #(duration * 1ms);
    SVX_TIME_US: #(duration * 1us);
    SVX_TIME_NS: #(duration * 1ns);
    SVX_TIME_PS: #(duration * 1ps);
    SVX_TIME_FS: #(duration * 1fs);
    default: $fatal(2, "SVX invalid delay unit code: %0d", unit_code);
  endcase
endtask

export "DPI-C" task delay_svx;

`endif
