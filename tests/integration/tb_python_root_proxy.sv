`include "sv/svx_pkg.sv"
`include ".tmp/python_root_proxy/root.sv"

module tb;
  import svx_pkg::*;
  import python_root_probe_pkg::*;
  initial begin
    Root value;
    Root failed_init;
    PlainRoot plain;
    Child child;
    Root base_handle;
    svx_dispatchable published;
    DerivedProxy sv_derived;
    GrandchildMirror grandchild;
    ChildMirror sv_child_view;
    int result;
    svx_init();
    svx_start("python_root.check_autoload");
    register_ChildMirror_factory();
    if (Root::scale(7) != 21 || Child::scale(7) != 28)
      $fatal(2, "root static dispatch required an instance or selected the child implementation");
    Root::wait_once();
    if ($time != 1)
      $fatal(2, "Python root static task did not advance simulation time");
    plain = new(13);
    if (plain.check(3) != 16)
      $fatal(2, "plain Python root virtual dispatch failed");
    svx_start("python_root.check_plain");
    svx_release_object(plain.__svx_remote_object_id);
    svx_start("python_root.check_plain_release");
    value = new(41);
    if (value.label != "quoted \"value\"\\path\n" || value.real_value != 2.5 ||
        value.short_value != -1.25 || int'(value.mode) != 7)
      $fatal(2, "SV-origin root lost declared String/Real/ShortReal/Enum defaults");
    $display("PYTHON_ROOT_DECLARED_DEFAULTS_SV_PASS");
    if (value.count != 41 || value.check(1) != 42)
      $fatal(2, "Python root construction/callback did not use SV-resident count");
    svx_start("python_root.check_owner");
    if (value.count != 42 || value.check(1) != 43)
      $fatal(2, "Python root field mutation did not update the real SV projection");
    svx_release_object(value.__svx_remote_object_id);
    svx_start("python_root.check_release");
    child = new(53);
    base_handle = child;
    if (base_handle.check(1) != 154 || child.base_check(1) != 54 ||
        base_handle.fixed(1) != 254 || child.fixed(1) != 354)
      $fatal(2, "SV child virtual or super dispatch did not reach the Python root correctly");
    if (base_handle.__svx_remote_object_id != child.__svx_remote_object_id)
      $fatal(2, "SV child and base handle did not preserve the paired identity");
    svx_start("python_root.check_child_owner");
    if (child.count != 54 || base_handle.check(1) != 155 || child.base_check(1) != 55)
      $fatal(2, "SV child and Python companion do not share the root field");
    svx_release_object(child.__svx_remote_object_id);
    svx_start("python_root.check_child_release");
    svx_start("python_root.check_python_origin_child");
    sv_child_view = new(81);
    base_handle = sv_child_view;
    if (base_handle.check(1) != 182 || sv_child_view.observed_root != 81 ||
        base_handle.fixed(1) != 282 || sv_child_view.fixed(1) != 382)
      $fatal(2, "shared C helper did not preserve direct SV-origin C semantics");
    svx_release_object(sv_child_view.__svx_remote_object_id);
    $display("PYTHON_ROOT_PROXY_PLANNED_C_PASS");
    svx_start("python_root.create_python_derived");
    svx_require_published_object("python_root.derived", published);
    if (!$cast(base_handle, published) || !$cast(child, published))
      $fatal(2, "Python derived object did not preserve the SV root/child types");
    if (base_handle.__svx_remote_object_id != child.__svx_remote_object_id)
      $fatal(2, "later Python portion created separate SV root/child identities");
    if (base_handle.check(1) != 1184 || child.check(1) != 1184 || child.base_check(1) != 84)
      $fatal(2, "later Python override or explicit C/root super dispatch failed");
    if (base_handle.fixed(1) != 284 || child.fixed(1) != 384)
      $fatal(2, "later Python portion changed nonvirtual SV method selection");
    child.count = 85;
    if (base_handle.check(1) != 1186 || child.observed_value() != 83)
      $fatal(2, "later Python override did not share the original SV fields");
    svx_release_object(base_handle.__svx_remote_object_id);
    svx_start("python_root.check_python_derived_release");
    if ($test$plusargs("ROOT_DERIVED_INIT_FAILURE")) begin
      sv_derived = new(88);
      $fatal(2, "failed derived constructor unexpectedly returned");
    end
    sv_derived = new(87);
    base_handle = sv_derived;
    if (sv_derived.observed_root != 87 || sv_derived.own_value != 1000 || base_handle.check(1) != 1188)
      $fatal(2, "SV-origin final companion or staged root/C/D initialization failed");
    svx_start("python_root.check_sv_derived");
    if (sv_derived.own_value != 2000 || sv_derived.child_value != 300 || base_handle.check(1) != 2388)
      $fatal(2, "SV-origin D fields do not share the final SV object storage");
    svx_release_object(sv_derived.__svx_remote_object_id);
    svx_start("python_root.check_sv_derived_release");
    register_GrandchildMirror_factory();
    svx_start("python_root.check_python_grandchild");
    grandchild = new(93);
    base_handle = grandchild;
    if (grandchild.observed_derived != 1000)
      $fatal(2, "SV-origin E did not initialize D before the E constructor body");
    result = base_handle.check(1);
    if (result != 1694)
      $fatal(2, "SV-origin E virtual result expected 1694, got %0d", result);
    svx_start("python_root.check_sv_grandchild");
    if (grandchild.own_value != 2000 || grandchild.e_value != 600 || base_handle.check(1) != 2794)
      $fatal(2, "SV-origin E virtual chain or shared field storage failed");
    svx_release_object(grandchild.__svx_remote_object_id);
    svx_start("python_root.check_sv_grandchild_release");
    svx_start("python_root.create_final");
    svx_require_published_object("python_root.final", published);
    if (!$cast(base_handle, published) || !$cast(grandchild, published))
      $fatal(2, "final Python receiver did not preserve its SV base handles");
    result = base_handle.check(1);
    if (result != 4696)
      $fatal(2, "final Python override expected 4696, got %0d", result);
    grandchild.count = 97;
    if (base_handle.check(1) != 4698)
      $fatal(2, "final Python override lost shared ancestor storage");
    svx_release_object(grandchild.__svx_remote_object_id);
    svx_start("python_root.check_final_release");
    // An already registered SV root supplies the storage for a failing Python initializer.
    failed_init = new(0, 77);
    svx_start("python_root.check_failed_initializer");
    if (failed_init.count != 99)
      $fatal(2, "SV field writes performed before failure were incorrectly rolled back");
    svx_release_object(failed_init.__svx_remote_object_id);
    if (Root::scale(9) != 27)
      $fatal(2, "root static method depended on a released companion");
    Root::wait_once();
    if ($time != 2)
      $fatal(2, "root static task did not remain callable after instance release");
    $display("PYTHON_ROOT_PROXY_STATIC_PASS");
    svx_start("python_root.check_shared_module");
    $display("PYTHON_ROOT_PROXY_SV_PASS");
    svx_shutdown();
    $finish;
  end
endmodule
