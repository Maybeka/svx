`ifndef SVX_PROCESS__SV
`define SVX_PROCESS__SV

class svx_process_manager#(string CATEGORY = "default");
  static process procs[int];
  static event completion_events[int];
  static event cancel_events[int];
  static bit cancel_requested_by_index[int];
  static int curr_id = -1;

  static function int add(process proc);
    automatic event completed;
    automatic event cancelled;
    curr_id++;
    procs[curr_id] = proc;
    completion_events[curr_id] = completed;
    cancel_events[curr_id] = cancelled;
    return curr_id;
  endfunction

  static function void remove(int index);
    if (completion_events.exists(index)) begin
      -> completion_events[index];
      completion_events.delete(index);
    end
    procs.delete(index);
    cancel_events.delete(index);
    cancel_requested_by_index.delete(index);
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

  static function void request_cancel(int index);
    if (procs.exists(index)) begin
      cancel_requested_by_index[index] = 1;
      -> cancel_events[index];
    end
  endfunction

  static function bit cancel_requested(int index);
    return cancel_requested_by_index.exists(index) &&
           cancel_requested_by_index[index];
  endfunction

  static task wait_for_cancel(int index);
    if (cancel_requested(index)) begin
      return;
    end
    @(cancel_events[index]);
  endtask

  static task await(int index);
    event completed;
    // Retain the event so removal can wake every outstanding waiter.
    if (completion_events.exists(index)) begin
      completed = completion_events[index];
      while (procs.exists(index)) @(completed);
    end
  endtask

  static task shutdown();
    int indices[$];
    // Cancel the whole wave before waiting; cleanup can create another wave.
    while (procs.num() != 0) begin
      indices.delete();
      foreach (procs[index]) begin
        indices.push_back(index);
        request_cancel(index);
      end
      foreach (indices[i]) await(indices[i]);
    end
  endtask
endclass

typedef svx_process_manager#("default") svx_proc_man;

import "DPI-C" context task svx_process__exec(chandle proc);
import "DPI-C" context function void svx_process__set_svobj_idx(chandle proc, int index);

function automatic int set_proc_index(chandle proc);
  process sv_proc = process::self();
  int index = svx_proc_man::add(sv_proc);
  svx_process__set_svobj_idx(proc, index);
  return index;
endfunction

task automatic start_process(chandle proc);
  int index;
  index = set_proc_index(proc);
  svx_process__exec(proc);
  if (svx_proc_man::cancel_requested(index)) begin
    // Kill this process's descendants, not other start_process invocations.
    disable fork;
  end
  svx_proc_man::remove(index);
endtask

function e_proc_state proc_status_svx(int index);
  return svx_proc_man::status(index);
endfunction

function void kill_proc_svx(int index);
  svx_proc_man::kill(index);
endfunction

function void request_cancel_proc_svx(int index);
  svx_proc_man::request_cancel(index);
endfunction

task await_proc_svx(int index);
  svx_proc_man::await(index);
endtask

export "DPI-C" function proc_status_svx;
export "DPI-C" function kill_proc_svx;
export "DPI-C" function request_cancel_proc_svx;
export "DPI-C" task await_proc_svx;

`endif
