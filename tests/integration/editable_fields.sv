// SPDX-License-Identifier: Apache-2.0
package editable_fields_pkg;
  class Driver;
    int count;
    int values[3];
    int history[$];
    int dynamic_values[];
    int mapping[int];
    function new();
      count = 1;
      values = '{10,20,30};
      history = '{1,2};
      dynamic_values = new[2];
      dynamic_values = '{4,5};
      mapping[7] = 70;
    endfunction
    function bit native_values_match();
      return count == 9 && values[1] == 22 && history.size() == 2 &&
             history[0] == 2 && history[1] == 3 && dynamic_values.size() == 3 &&
             dynamic_values[2] == 6 && mapping[7] == 77;
    endfunction
  endclass
endpackage
