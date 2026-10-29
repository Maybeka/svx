`ifndef UVMX_FACTORY__SV
`define UVMX_FACTORY__SV

class uvmx_test_bridge#(type BASE = uvm_test) extends BASE;
  local uvmx_phase_callbacks callbacks;
  local string python_test_name;
  local uvm_object_wrapper python_wrapper;

  function new(string name = "uvmx_test_bridge", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void bind_python_test(string canonical_id, string factory_name,
                                 uvm_object_wrapper wrapper);
    if (callbacks != null) begin
      `uvm_fatal("UVMX/BIND", "Python Test is already bound to this bridge")
      return;
    end
    python_test_name = factory_name;
    python_wrapper = wrapper;
    callbacks = new(canonical_id);
  endfunction

  virtual function string get_type_name();
    if (python_wrapper == null) return super.get_type_name();
    return python_test_name;
  endfunction

  virtual function uvm_object_wrapper get_object_type();
    if (python_wrapper == null) return super.get_object_type();
    return python_wrapper;
  endfunction

  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    callbacks.build_phase();
  endfunction
  virtual function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);
    callbacks.connect_phase();
  endfunction
  virtual function void end_of_elaboration_phase(uvm_phase phase);
    super.end_of_elaboration_phase(phase);
    callbacks.end_of_elaboration_phase();
  endfunction
  virtual function void start_of_simulation_phase(uvm_phase phase);
    super.start_of_simulation_phase(phase);
    callbacks.start_of_simulation_phase();
  endfunction
  virtual task run_phase(uvm_phase phase);
    super.run_phase(phase);
    phase.raise_objection(this, "Python test active");
    callbacks.run_phase();
    phase.drop_objection(this, "Python test completed");
  endtask
endclass

class uvmx_test_wrapper#(type BASE = uvm_test) extends uvm_object_wrapper;
  local string factory_name;
  local string canonical_id;

  function new(string factory_name, string canonical_id);
    this.factory_name = factory_name;
    this.canonical_id = canonical_id;
  endfunction
  virtual function string get_type_name();
    return factory_name;
  endfunction
  virtual function uvm_component create_component(string name, uvm_component parent);
    uvmx_test_bridge#(BASE) instance;
    instance = new(name, parent);
    instance.bind_python_test(canonical_id, factory_name, this);
    return instance;
  endfunction
endclass

virtual class uvmx_base_factory;
  pure virtual function uvm_object_wrapper make(string name, string canonical_id);
endclass

class uvmx_typed_base_factory#(type BASE = uvm_test) extends uvmx_base_factory;
  virtual function uvm_object_wrapper make(string name, string canonical_id);
    uvmx_test_wrapper#(BASE) wrapper = new(name, canonical_id);
    return wrapper;
  endfunction
endclass

class uvmx_base_registry;
  static uvmx_base_factory bases[string];

  static function void add(string sv_base, uvmx_base_factory factory);
    if (bases.exists(sv_base))
      `uvm_fatal("UVMX/BASE", {"duplicate SV base bridge: ", sv_base})
    bases[sv_base] = factory;
  endfunction

  static function void register_test(UvmxRegistration declaration);
    uvm_factory factory = uvm_factory::get();
    uvm_object_wrapper wrapper;
    if (!bases.exists(declaration.sv_base))
      `uvm_fatal("UVMX/BASE", {"SV base bridge was not compiled: ", declaration.sv_base})
    wrapper = bases[declaration.sv_base].make(declaration.factory_name, declaration.canonical_id);
    factory.register(wrapper);
    if (factory.find_wrapper_by_name(declaration.factory_name) != wrapper)
      `uvm_fatal("UVMX/NAME", {"Python test conflicts with an existing UVM factory name: ", declaration.factory_name})
  endfunction
endclass

`endif
