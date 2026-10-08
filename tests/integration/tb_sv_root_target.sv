`include "sv/svx_pkg.sv"
`include ".tmp/sv_root_target/common.svh"
`ifdef SV_ROOT_PREFIX
package sv_root_prefix_pkg;
  class Z;
    int prefix_count = 400;
    static int allocations;
    function new();
      allocations++;
    endfunction
    protected function int prefix_value();
      return prefix_count;
    endfunction
    virtual function int prefix_virtual();
      return prefix_count;
    endfunction
    protected static function int prefix_scale();
      return 800;
    endfunction
  endclass
endpackage
`endif
package sv_root_pkg;
  typedef class A;
  virtual class Creator;
    pure virtual function A create();
  endclass
`ifdef SV_ROOT_PREFIX
  class A extends sv_root_prefix_pkg::Z;
`else
  class A;
`endif
    int count = 11;
    static Creator creator;
    static bit create_nested;
    A nested;
    function new();
      if (create_nested) begin
        create_nested = 0;
        nested = creator.create();
      end
    endfunction
    virtual function int check();
      return count;
    endfunction
`ifdef SV_ROOT_ORDINARY_MIDDLE
    static function int root_scale(int value);
      return value * 2;
    endfunction
`endif
  endclass
endpackage
`include ".tmp/sv_root_target/a.svh"
`include ".tmp/sv_root_target/b.svh"
`ifdef SV_ROOT_ORDINARY_MIDDLE
package sv_root_middle_pkg;
  class Middle extends svx_proxy_sv_root_target_test::B;
    int middle = 300;
    static int allocations;
    function new();
      super.new();
      allocations++;
    endfunction
    virtual function int check();
      return super.check() + middle;
    endfunction
    protected function int middle_value();
      return middle;
    endfunction
    protected static function int middle_scale(int value);
      return value * 3;
    endfunction
    static function int scale(int value);
      return value * 3;
    endfunction
    protected static task middle_wait();
      #1;
    endtask
  endclass
endpackage
`endif
package sv_root_child_pkg;
`ifdef SV_ROOT_ORDINARY_MIDDLE
  class C extends sv_root_middle_pkg::Middle;
`else
  class C extends svx_proxy_sv_root_target_test::B;
`endif
    int extra = 100;
`ifdef SV_ROOT_ORDINARY_MIDDLE
    static function int scale(int value);
      return value * 4;
    endfunction
`endif
`ifdef SV_ROOT_IMPLICIT_CONSTRUCTORS
    int observed = retry;
`else
    int observed;
    function new();
      super.new();
      observed = retry;
    endfunction
`endif
`ifndef SV_ROOT_INHERITED_SLOT
    virtual function int check();
      return super.check() + extra;
    endfunction
`endif
    function int observed_value();
      return observed;
    endfunction
  endclass
endpackage
`include ".tmp/sv_root_target/c.svh"
package sv_root_nested_creator_pkg;
  class Creator extends sv_root_pkg::Creator;
    virtual function sv_root_pkg::A create();
      svx_mirror_sv_sv_root_child_pkg_C::C value = new();
      return value;
    endfunction
  endclass
endpackage
`ifdef SV_ROOT_EXTENDED
`include ".tmp/sv_root_target/d.svh"
package sv_root_e_pkg;
  class E extends svx_proxy_sv_root_target_derived::D;
    int e_value = 500;
`ifdef SV_ROOT_IMPLICIT_CONSTRUCTORS
    int observed_d = own;
`else
    int observed_d;
    function new();
      super.new();
      observed_d = own;
    endfunction
`endif
    virtual function int check();
      return super.check() + e_value;
    endfunction
    function int observed_python();
      return observed_d;
    endfunction
  endclass
endpackage
`include ".tmp/sv_root_target/e.svh"
`endif
`ifndef SV_ROOT_DECLARATIONS_ONLY
module tb;
  import svx_pkg::*;
  initial begin
    sv_root_child_pkg::C python_c;
    svx_mirror_sv_sv_root_child_pkg_C::C sv_c;
    svx_mirror_sv_sv_root_pkg_A::A direct_a;
    sv_root_pkg::A base_handle;
    sv_root_nested_creator_pkg::Creator creator;
    svx_mirror_sv_sv_root_child_pkg_C::C nested_c;
`ifdef SV_ROOT_EXTENDED
    sv_root_child_pkg::C python_d;
    sv_root_e_pkg::E python_e;
    svx_mirror_sv_sv_root_e_pkg_E::E sv_e;
`endif
    svx_init();
    svx_start("sv_root_target.create_direct");
    `SVX_GET_OBJECT(svx_mirror_sv_sv_root_pkg_A::A, "sv_root_target.direct_b", direct_a)
    if (direct_a.check() != 35) $fatal(1, "direct B callback failed");
    svx_start("sv_root_target.verify_direct");
    svx_release_object(direct_a.__svx_remote_object_id);
    svx_start("sv_root_target.verify_direct_closed");
    if ($test$plusargs("SV_ROOT_NESTED_CONSTRUCTOR")) begin
      creator = new();
      sv_root_pkg::A::creator = creator;
      sv_root_pkg::A::create_nested = 1;
    end
    if ($test$plusargs("SV_ROOT_PYTHON_INIT_FAILURE"))
      svx_start("sv_root_target.fail_next_init");
    svx_start("sv_root_target.create");
    `SVX_GET_OBJECT(sv_root_child_pkg::C, "sv_root_target.c", python_c)
    if (svx_construction_context::frames.size() != 0)
      $fatal(1, "constructor context leaked after Python C");
    if ($test$plusargs("SV_ROOT_NESTED_CONSTRUCTOR")) begin
      if (!$cast(nested_c, python_c.nested) || nested_c.__svx_remote_object_id == python_c.__svx_remote_object_id)
        $fatal(1, "nested same-type constructor stole the outer object ID");
      svx_start("sv_root_target.verify_nested");
    end
    base_handle = python_c;
    if (python_c.check() != 135 || python_c.observed != 23 || base_handle.check() != 135)
      $fatal(1, "SV-root final receiver dispatch/construction failed");
    python_c.count = 19;
    svx_start("sv_root_target.close");
    if ($test$plusargs("SV_ROOT_SV_INIT_FAILURE"))
      svx_start("sv_root_target.fail_next_init");
    sv_c = new();
    if (sv_c.check() != 135 || sv_c.observed != 23)
      $fatal(1, "SV-origin final receiver dispatch/construction failed");
    svx_start("sv_root_target.verify_sv");
`ifdef SV_ROOT_EXTENDED
    svx_start("sv_root_target.create_d");
    `SVX_GET_OBJECT(sv_root_child_pkg::C, "sv_root_target.d", python_d)
    base_handle = python_d;
    if (base_handle.check() != 1135) $fatal(1, "D override chain failed");
    svx_start("sv_root_target.close_d");
    if ($test$plusargs("SV_ROOT_E_PYTHON_INIT_FAILURE"))
      svx_start("sv_root_target.fail_next_late_init");
    if ($test$plusargs("SV_ROOT_E_PYTHON_INNER_FAILURE"))
      svx_start("sv_root_target.fail_next_init");
    svx_start("sv_root_target.create_e");
    `SVX_GET_OBJECT(sv_root_e_pkg::E, "sv_root_target.e", python_e)
    base_handle = python_e;
    if (base_handle.check() != 1635 || python_e.observed_d != 1000)
      $fatal(1, "E override/construction chain failed");
    python_e.own = 2000;
    svx_start("sv_root_target.close_e");
    if ($test$plusargs("SV_ROOT_E_SV_INIT_FAILURE"))
      svx_start("sv_root_target.fail_next_late_init");
    if ($test$plusargs("SV_ROOT_E_SV_INNER_FAILURE"))
      svx_start("sv_root_target.fail_next_init");
    sv_e = new();
    if (sv_e.check() != 1635 || sv_e.observed_d != 1000)
      $fatal(1, "SV-origin E construction failed");
    svx_start("sv_root_target.verify_sv_e");
`endif
    if (svx_construction_context::frames.size() != 0)
      $fatal(1, "constructor context leaked after complete chain");
    svx_shutdown();
    $display("SV_ROOT_TARGET_PASS");
    $finish;
  end
  final begin
    if ($test$plusargs("SV_ROOT_PYTHON_INIT_FAILURE") || $test$plusargs("SV_ROOT_SV_INIT_FAILURE") ||
        $test$plusargs("SV_ROOT_E_PYTHON_INIT_FAILURE") || $test$plusargs("SV_ROOT_E_SV_INIT_FAILURE") ||
        $test$plusargs("SV_ROOT_E_PYTHON_INNER_FAILURE") || $test$plusargs("SV_ROOT_E_SV_INNER_FAILURE")) begin
      if (svx_inheritance_registry::objects.num() != 0 || svx_construction_context::frames.size() != 0 ||
          svx_proxy_sv_root_target_test::B_constructor_arguments::prepared.num() != 0)
        $fatal(1, "failed constructor retained root state");
`ifdef SV_ROOT_EXTENDED
      if (svx_proxy_sv_root_target_derived::D_constructor_arguments::prepared.num() != 0)
        $fatal(1, "failed constructor retained outer state");
`endif
      $display("SV_ROOT_CONSTRUCTOR_ROLLBACK_SV_PASS");
    end
  end
endmodule
`endif
