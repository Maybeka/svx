package source_formals_pkg;
  class Formals;
    function void inspect(input int a, output b, c, input d);
      if ($bits(a) != 32 || $bits(b) != 1 || $bits(c) != 1 || $bits(d) != 1)
        $fatal(1, "explicit direction did not reset the implicit type");
      b = a[0];
      c = d;
    endfunction

    function int inspect_arrays(input int values[$], output int samples[3]);
      foreach (samples[i]) samples[i] = values[i];
      return values.size();
    endfunction
  endclass
endpackage

module tb;
  initial begin
    source_formals_pkg::Formals value = new;
    int values[$] = '{11, 12, 13};
    int samples[3];
    logic first, second;
    value.inspect(3, first, second, 0);
    if (first !== 1 || second !== 0) $fatal(1, "formal copy-out mismatch");
    if (value.inspect_arrays(values, samples) != 3) $fatal(1, "queue formal mismatch");
    foreach (samples[i])
      if (samples[i] != values[i]) $fatal(1, "array formal copy-out mismatch");
    $display("SOURCE_FORMALS_PASS");
    $finish;
  end
endmodule
