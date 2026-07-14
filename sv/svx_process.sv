`ifndef SVX_PROCESS__SV
`define SVX_PROCESS__SV

class svx_process_manager#(string CATEGORY = "default");
  static process procs[int];
  static int curr_id = -1;

  static function int add(process proc);
    curr_id++;
    procs[curr_id] = proc;
    return curr_id;
  endfunction

  static function void remove(int index);
    procs.delete(index);
  endfunction

  static function e_proc_state status(int index);
    if (procs.exists(index)) begin
      return e_proc_state'(procs[index].status());
    end
    return index inside {[0:curr_id]} ? REMOVED : NOT_CREATED;
  endfunction

  static function void kill(int index);
    if (procs.exists(index)) begin
      procs[index].kill();
      remove(index);
    end
  endfunction

  static task await(int index);
    if (procs.exists(index)) begin
      procs[index].await();
      remove(index);
    end
  endtask
endclass

typedef svx_process_manager#("default") svx_proc_man;

import "DPI-C" context task svx_process__exec(chandle proc);
import "DPI-C" context function void svx_process__set_svobj_idx(chandle proc, int index);

function automatic void set_proc_index(chandle proc);
  process sv_proc = process::self();
  int index = svx_proc_man::add(sv_proc);
  svx_process__set_svobj_idx(proc, index);
endfunction

task automatic start_process(chandle proc);
  set_proc_index(proc);
  svx_process__exec(proc);
endtask

function e_proc_state proc_status_svx(int index);
  return svx_proc_man::status(index);
endfunction

function void kill_proc_svx(int index);
  svx_proc_man::kill(index);
endfunction

task await_proc_svx(int index);
  svx_proc_man::await(index);
endtask

export "DPI-C" function proc_status_svx;
export "DPI-C" function kill_proc_svx;
export "DPI-C" task await_proc_svx;

`endif
