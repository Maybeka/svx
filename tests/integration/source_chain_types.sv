package source_chain_pkg;
  class A;
    int count;
    virtual function int check(input int value);
      return count + value;
    endfunction
  endclass
endpackage

package source_chain_bridge_pkg;
  `SVX_PY_PROXY(BProxy, "py://tests/integration/source_chain_base/B", source_chain_pkg::A)
endpackage

package source_chain_user_pkg;
  class C extends source_chain_bridge_pkg::BProxy;
    function int check(input int value);
      return super.check(value) + 100;
    endfunction
    function int compute(input int value);
      return super.compute(value) + 1000;
    endfunction
  endclass
endpackage
