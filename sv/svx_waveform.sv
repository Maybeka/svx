`ifndef SVX_WAVEFORM__SV
`define SVX_WAVEFORM__SV

// Keep unsupported backend task names out of the compilation entirely.
`ifdef SVX_ENABLE_FSDB_WAVEFORM
function automatic int unsigned svx_waveform_bridge_abi();
  return 1;
endfunction

task automatic svx_waveform_execute(int operation, string path, int depth);
  case (operation)
    1: $fsdbDumpfile(path);
    2: $fsdbDumpvars("level=", depth, "instance=", path);
    3: $fsdbDumpoff;
    4: $fsdbDumpon;
    5: $fsdbDumpflush;
    6: $fsdbSwitchDumpfile(path);
    7: $fsdbDumpFinish;
    default: $fatal(1, "SVX invalid waveform operation: %0d", operation);
  endcase
endtask

export "DPI-C" function svx_waveform_bridge_abi;
export "DPI-C" task svx_waveform_execute;
`endif

`endif
