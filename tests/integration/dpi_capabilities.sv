// SPDX-License-Identifier: Apache-2.0
package dpi_capabilities_pkg;
  typedef enum bit [1:0] { ZERO = 0, ONE = 1 } Mode;
  typedef struct packed { bit [7:0] first; bit [7:0] second; } Pair;
  import "DPI-C" function int dpi_scalar(input int value, output int doubled, inout int total);
  import "DPI-C" function void dpi_logic(input logic [7:0] value, output logic [7:0] result);
  import "DPI-C" function string dpi_text(input string value);
  import "DPI-C" function void dpi_mode(input Mode value, output Mode result);
  import "DPI-C" function void dpi_pair(input Pair value, output Pair result);
  import "DPI-C" task dpi_task(input int value, output int result, inout int total);
  import "DPI-C" function void dpi_arrays(input int unsigned source[], inout int unsigned changed[]);
  function automatic void sv_output(input int count, output int unsigned result[]);
    result = new[count];
    foreach (result[i]) result[i] = 100 + i;
  endfunction
  task automatic sv_task_output(input int count, output int unsigned result[]);
    #1ns;
    result = new[count];
    foreach (result[i]) result[i] = 200 + i;
  endtask
endpackage
