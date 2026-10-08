package constructor_order_pkg;
  class Trace;
    static string events[$];
    static function int note(string message);
      events.push_back(message);
      $display("CONSTRUCTOR_ORDER:%s", message);
      return events.size();
    endfunction
  endclass
  class A;
    int a_field = Trace::note("A field");
    function new();
      void'(Trace::note("A body"));
    endfunction
  endclass
  class AMirror extends A;
    int claimed_id = capture();
    virtual function string target();
      return "A";
    endfunction
    function int capture();
      return Trace::note({"mirror field target=", this.target()});
    endfunction
    function new();
      int local_marker = Trace::note({"AMirror local target=", this.target()});
      super.new();
      void'(Trace::note("AMirror body"));
    endfunction
  endclass
  class C extends AMirror;
    int c_field = Trace::note("C field");
    function new();
      super.new();
      void'(Trace::note("C body"));
    endfunction
  endclass
  class CMirror extends C;
    int final_field = Trace::note("CMirror field");
    virtual function string target();
      return "C";
    endfunction
    function new();
      int local_marker = Trace::note({"CMirror local target=", this.target()});
      super.new();
      void'(Trace::note("CMirror body"));
    endfunction
  endclass
endpackage
module tb;
  initial begin
    constructor_order_pkg::CMirror value;
    value = new();
    if (value.claimed_id == 0 || constructor_order_pkg::Trace::events.size() != 10)
      $fatal(1, "constructor field initializer was not executed exactly once");
    $display("CONSTRUCTOR_ORDER_PROBE_PASS");
    $finish;
  end
endmodule
