class RegisterChecker extends svx_proxy_extensions::Checker;
  int sv_calls;

  function new(longint unsigned object_id, int seed);
    super.new(object_id);
    sv_calls = 0;
  endfunction

  virtual function bit [0:0] compare(bit [31:0] expected, bit [31:0] actual);
    sv_calls++;
    return super.compare(expected, actual);
  endfunction

  virtual task finish();
    if (sv_calls != 8) $fatal(2, "REGISTER_LAB_CHECKER_COUNT expected=8 actual=%0d", sv_calls);
    #0.05ns;
    super.finish();
  endtask
endclass
