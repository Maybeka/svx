module enum_owner #(int W = 9);
  for (genvar i = 0; i < 1; i++) begin: lane
    class Driver;
      typedef enum bit signed [W-1:0] {IDLE=0, ACTIVE=-1} State;
      State state;

      function new(State initial_state);
        state = initial_state;
      endfunction

      virtual function State echo_state(input State value, output State previous, inout State changed);
        previous = state;
        state = value;
        changed = value;
        return state;
      endfunction

      task step(input State value, output State previous, inout State changed);
        #1ns;
        previous = state;
        state = value;
        changed = value;
      endtask

      static function State active_state();
        return ACTIVE;
      endfunction

      static function State call_echo_state(Driver item, input State value,
                                            output State previous, inout State changed);
        return item.echo_state(value, previous, changed);
      endfunction
    endclass
  end
endmodule
