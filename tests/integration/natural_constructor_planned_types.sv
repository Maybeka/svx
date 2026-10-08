package natural_bridge_proxy_pkg;
  `SVX_PY_PROXY(BProxy, "py://tests/integration/natural_constructor_bridge/B", natural_bridge_pkg::A)
endpackage

package natural_bridge_child_pkg;
  class C extends natural_bridge_proxy_pkg::BProxy;
    function new(int seed, string label, natural_bridge_pkg::Packet packet);
      super.new(seed + 10, {label, "-C"}, packet, 2);
      count += 1000;
    endfunction
  endclass
endpackage
