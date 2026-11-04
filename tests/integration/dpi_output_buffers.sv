package dpi_output_buffers_pkg;
  import "DPI-C" function void fill(output int unsigned values[]);
  import "DPI-C" task fill_task(output int unsigned values[]);
  import "DPI-C" function void fill_pair(output int unsigned left[], output int unsigned right[]);
  function automatic void ordinary(output int unsigned values[]);
    values = new[3];
    values = '{11, 22, 33};
  endfunction
endpackage
